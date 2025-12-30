#!/usr/bin/env python3
"""
SRT Gateway Router - Hot Reload Per Session
"""
import ctypes
import ctypes.util
import threading
import time
import json
import socket
import struct
import os
import sqlite3
import glob
import collections
from typing import Dict, List, Optional

# Load libsrt
libsrt_path = ctypes.util.find_library('srt')
if not libsrt_path:
    libsrt_path = '/usr/lib/x86_64-linux-gnu/libsrt-gnutls.so.1.5.3'
libsrt = ctypes.CDLL(libsrt_path)

# SRT Constants
SRTO_LATENCY = 22
SRTO_PASSPHRASE = 23
SRTO_PBKEYLEN = 24
SRTO_STREAMID = 30
SRTO_MAXBW = 31
SRTO_SNDBUF = 13
SRTO_RCVBUF = 14
SRTO_RENDEZVOUS = 12
SRT_INVALID_SOCK = -1
AF_INET = socket.AF_INET

# Setup libsrt
libsrt.srt_startup.restype = ctypes.c_int
libsrt.srt_create_socket.restype = ctypes.c_int
libsrt.srt_bind.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
libsrt.srt_bind.restype = ctypes.c_int
libsrt.srt_listen.argtypes = [ctypes.c_int, ctypes.c_int]
libsrt.srt_listen.restype = ctypes.c_int
libsrt.srt_accept.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
libsrt.srt_accept.restype = ctypes.c_int
libsrt.srt_close.argtypes = [ctypes.c_int]
libsrt.srt_close.restype = ctypes.c_int
libsrt.srt_recv.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
libsrt.srt_recv.restype = ctypes.c_int
libsrt.srt_send.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
libsrt.srt_send.restype = ctypes.c_int
libsrt.srt_setsockopt.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
libsrt.srt_setsockopt.restype = ctypes.c_int

class BitrateCalculator:
    def __init__(self):
        self.bytes = 0
        self.last_bytes = 0
        self.last_time = time.time()
        self.mbps = 0.0
        self.lock = threading.Lock()

    def add(self, n: int):
        with self.lock:
            self.bytes += n

    def calculate(self) -> float:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_time
            if elapsed < 0.5:
                return self.mbps

            bytes_diff = self.bytes - self.last_bytes
            self.mbps = round((bytes_diff * 8) / elapsed / 1_000_000, 2) if bytes_diff > 0 else 0.0
            self.last_bytes = self.bytes
            self.last_time = now
            return self.mbps

class HistoricalDataBuffer:
    """Stores historical data points for graphing (circular buffer)"""
    def __init__(self, max_points: int = 300):
        self.max_points = max_points
        self.data = []
        self.timestamps = []
        self.lock = threading.Lock()
    
    def add(self, value: float):
        """Add a data point (keeps last max_points)"""
        with self.lock:
            self.data.append(value)
            self.timestamps.append(time.time())
            if len(self.data) > self.max_points:
                self.data.pop(0)  # Remove oldest
                self.timestamps.pop(0)
    
    def get(self) -> List[float]:
        """Get all data points"""
        with self.lock:
            return self.data.copy()
    
    def get_with_timestamps(self) -> dict:
        """Get data points with timestamps"""
        with self.lock:
            return {
                'values': self.data.copy(),
                'timestamps': self.timestamps.copy()
            }
    
    def clear(self):
        """Clear all data"""
        with self.lock:
            self.data.clear()
            self.timestamps.clear()

class AdaptiveBuffer:
    """
    Adaptive Buffer for handling variable network conditions (e.g., Starlink)
    Monitors network health and dynamically adjusts buffering
    """
    def __init__(self, enabled: bool = False, weight_loss: int = 40, 
                 weight_buffer: int = 30, weight_jitter: int = 20, weight_rtt: int = 10,
                 max_buffer_ms: int = 2000):
        self.enabled = enabled
        if not self.enabled:
            return
        
        # Configuration
        self.weights = {
            'loss': weight_loss,
            'buffer': weight_buffer,
            'jitter': weight_jitter,
            'rtt': weight_rtt
        }
        
        # Buffer settings
        self.queue = collections.deque()
        self.max_buffer_ms = max_buffer_ms  # Use configured max buffer
        self.max_queue_size = 10000  # ~15MB at 1500 bytes/packet
        
        # State
        self.mode = "PASS_THROUGH"  # PASS_THROUGH, BUFFERING, RELEASING
        self.health_score = 100
        self.target_buffer_ms = 0
        self.current_buffer_ms = 0
        
        # Network baseline
        self.baseline_rtt = None
        self.prev_rtt = 0
        self.prev_loss = 0
        self.prev_packets_sent = 0
        
        # Timing
        self.last_health_check = time.time()
        self.last_send = time.time()
        self.last_mode_change = time.time()
        
        # Statistics
        self.packets_buffered = 0
        self.packets_dropped_overflow = 0
        self.bad_score_count = 0
        
        # Thread safety
        self.lock = threading.Lock()
    
    def add_packet(self, packet_data: bytes):
        """Add packet to buffer (or pass through if disabled/mode allows)"""
        if not self.enabled:
            return packet_data  # Pass through immediately
        
        with self.lock:
            # Add to queue with timestamp
            self.queue.append({
                'data': packet_data,
                'timestamp': time.time()
            })
            self.packets_buffered += 1
            
            # Overflow protection
            if len(self.queue) > self.max_queue_size:
                self.queue.popleft()
                self.packets_dropped_overflow += 1
            
            return None  # Signal that packet was buffered
    
    def update_health(self, stats: dict):
        """Update network health score based on SRT statistics"""
        if not self.enabled:
            return
        
        now = time.time()
        
        # Check every 100ms
        if now - self.last_health_check < 0.1:
            return
        
        with self.lock:
            self.last_health_check = now
            
            try:
                # Extract metrics
                current_rtt = stats.get('msRTT', 0)
                current_loss_total = stats.get('pktSndLoss', 0)
                packets_sent = stats.get('pktSent', 0)
                buffer_avail = stats.get('byteAvailSndBuf', 0)
                buffer_total = stats.get('pktSndBuf', 0) * 1500  # Estimate total buffer size
                
                # Set baseline RTT on first reading
                if self.baseline_rtt is None and current_rtt > 0:
                    self.baseline_rtt = current_rtt
                
                # Calculate metrics
                # 1. Loss rate (last 100ms)
                packets_sent_delta = max(0, packets_sent - self.prev_packets_sent)
                loss_delta = max(0, current_loss_total - self.prev_loss)
                loss_rate = (loss_delta / packets_sent_delta * 100) if packets_sent_delta > 0 else 0
                
                # 2. Buffer usage
                buffer_usage = ((buffer_total - buffer_avail) / buffer_total * 100) if buffer_total > 0 else 0
                
                # 3. Jitter (RTT variance)
                jitter = abs(current_rtt - self.prev_rtt) if self.prev_rtt > 0 else 0
                
                # 4. RTT score (ratio to baseline)
                rtt_ratio = (current_rtt / self.baseline_rtt) if self.baseline_rtt and self.baseline_rtt > 0 else 1.0
                
                # Calculate health score
                score = 100
                
                # Loss penalty (scaled by weight)
                loss_penalty = 0
                if loss_rate > 1.0:
                    loss_penalty = 50
                elif loss_rate > 0.5:
                    loss_penalty = 30
                elif loss_rate > 0.2:
                    loss_penalty = 15
                score -= (loss_penalty * self.weights['loss'] / 40)
                
                # Buffer usage penalty (scaled by weight)
                buffer_penalty = 0
                if buffer_usage > 80:
                    buffer_penalty = 40
                elif buffer_usage > 50:
                    buffer_penalty = 20
                elif buffer_usage > 30:
                    buffer_penalty = 10
                score -= (buffer_penalty * self.weights['buffer'] / 30)
                
                # Jitter penalty (scaled by weight)
                jitter_penalty = 0
                if jitter > 50:
                    jitter_penalty = 20
                elif jitter > 20:
                    jitter_penalty = 10
                score -= (jitter_penalty * self.weights['jitter'] / 20)
                
                # RTT penalty (scaled by weight)
                rtt_penalty = 0
                if rtt_ratio > 3.0:
                    rtt_penalty = 15
                elif rtt_ratio > 2.0:
                    rtt_penalty = 10
                score -= (rtt_penalty * self.weights['rtt'] / 10)
                
                self.health_score = max(0, min(100, score))
                
                # Update mode based on health score
                self._update_mode()
                
                # Update previous values
                self.prev_rtt = current_rtt
                self.prev_loss = current_loss_total
                self.prev_packets_sent = packets_sent
                
            except Exception as e:
                print(f"⚠️  AB health update error: {e}")
    
    def _update_mode(self):
        """Update buffering mode based on health score"""
        now = time.time()
        
        # Prevent rapid mode switching
        if now - self.last_mode_change < 2.0:
            return
        
        old_mode = self.mode
        
        if self.health_score >= 80:
            # Good conditions - pass through
            if self.bad_score_count > 0:
                self.bad_score_count -= 1
            self.target_buffer_ms = 0
            self.mode = "PASS_THROUGH"
        
        elif self.health_score >= 50:
            # Warning - start buffering
            self.bad_score_count = 0
            # Progressive buffer target based on score
            self.target_buffer_ms = int((80 - self.health_score) / 30 * 1500)
            self.mode = "BUFFERING"
        
        else:
            # Bad conditions - use full buffer
            self.bad_score_count += 1
            if self.bad_score_count >= 3:  # Require 3 consecutive bad scores
                self.target_buffer_ms = self.max_buffer_ms
                self.mode = "RELEASING"
        
        if old_mode != self.mode:
            self.last_mode_change = now
            # Log mode change
            if self.mode == "PASS_THROUGH":
                print(f"🟢 AB: GOOD → Pass-through ({self.get_current_latency_ms()}ms)")
            elif self.mode == "BUFFERING":
                print(f"🟡 AB: WARNING → Buffering (health: {self.health_score:.0f}, target: {self.target_buffer_ms}ms)")
            elif self.mode == "RELEASING":
                print(f"🔴 AB: BAD → Releasing buffer ({self.target_buffer_ms}ms)")
    
    def get_packets_to_send(self) -> list:
        """Get packets that are ready to be sent"""
        if not self.enabled:
            return []
        
        with self.lock:
            now = time.time()
            packets_to_send = []
            
            if self.mode == "PASS_THROUGH":
                # Send all immediately
                while self.queue:
                    packets_to_send.append(self.queue.popleft()['data'])
                self.current_buffer_ms = 0
            
            elif self.mode == "BUFFERING":
                # Build buffer - send at reduced rate
                if len(self.queue) > 0:
                    # Calculate current buffer size
                    oldest_timestamp = self.queue[0]['timestamp']
                    self.current_buffer_ms = (now - oldest_timestamp) * 1000
                    
                    if self.current_buffer_ms >= self.target_buffer_ms:
                        # Target reached, send at normal rate
                        if now - self.last_send >= 0.001:  # 1ms interval
                            packets_to_send.append(self.queue.popleft()['data'])
                            self.last_send = now
                    else:
                        # Still building buffer - send slower
                        if now - self.last_send >= 0.0012:  # 1.2ms interval (20% slower)
                            if self.queue:
                                packets_to_send.append(self.queue.popleft()['data'])
                                self.last_send = now
            
            elif self.mode == "RELEASING":
                # Release from buffer at normal rate
                if now - self.last_send >= 0.001:  # 1ms interval
                    if self.queue:
                        packets_to_send.append(self.queue.popleft()['data'])
                        self.last_send = now
                    
                    # Update current buffer
                    if self.queue:
                        oldest_timestamp = self.queue[0]['timestamp']
                        self.current_buffer_ms = (now - oldest_timestamp) * 1000
                    else:
                        self.current_buffer_ms = 0
            
            return packets_to_send
    
    def get_current_latency_ms(self) -> int:
        """Get current buffer latency in milliseconds"""
        if not self.enabled or self.mode == "PASS_THROUGH":
            return 35  # Baseline network latency
        return int(self.current_buffer_ms)
    
    def get_stats(self) -> dict:
        """Get adaptive buffer statistics"""
        if not self.enabled:
            return {'enabled': False}
        
        with self.lock:
            return {
                'enabled': True,
                'mode': self.mode,
                'health_score': round(self.health_score, 1),
                'current_latency_ms': self.get_current_latency_ms(),
                'target_buffer_ms': self.target_buffer_ms,
                'packets_buffered': len(self.queue),
                'packets_dropped': self.packets_dropped_overflow,
                'weights': self.weights.copy()
            }

class TXOutput:
    def __init__(self, route_id: int, port: int, mode: str, host: str,
                 remote_port: Optional[int], streamid: Optional[str], maxbw: Optional[int],
                 latency: int, passphrase: Optional[str], buffer: int,
                 adaptive_buffer_enabled: bool = False, ab_weight_loss: int = 40,
                 ab_weight_buffer: int = 30, ab_weight_jitter: int = 20, ab_weight_rtt: int = 10,
                 ab_max_buffer_ms: int = 2000):
        self.route_id = route_id
        self.port = port
        self.mode = mode
        self.host = host
        self.remote_port = remote_port
        self.streamid = streamid
        self.maxbw = maxbw
        self.latency = latency
        self.passphrase = passphrase
        self.buffer = buffer

        self.listener_socket = SRT_INVALID_SOCK
        self.decoder_sockets: List[int] = []
        self.bitrate = BitrateCalculator()
        self.bitrate_history = HistoricalDataBuffer(300)  # Last 5 minutes
        self.running = True
        self.lock = threading.Lock()

        self.packets_sent = 0
        self.packets_lost = 0
        self.packets_sent_history = HistoricalDataBuffer(300)
        self.rtt = 0.0
        self.rtt_history = HistoricalDataBuffer(300)  # Track RTT over time
        
        # Adaptive Buffer
        self.adaptive_buffer = AdaptiveBuffer(
            enabled=adaptive_buffer_enabled,
            weight_loss=ab_weight_loss,
            weight_buffer=ab_weight_buffer,
            weight_jitter=ab_weight_jitter,
            weight_rtt=ab_weight_rtt,
            max_buffer_ms=ab_max_buffer_ms
        )
        
        # Start buffer processing thread if AB enabled
        if adaptive_buffer_enabled:
            self.buffer_thread = threading.Thread(target=self._process_buffer, daemon=True)
            self.buffer_thread.start()

    def _process_buffer(self):
        """Background thread to process adaptive buffer"""
        while self.running:
            try:
                # Get packets ready to send
                packets = self.adaptive_buffer.get_packets_to_send()
                
                for packet_data in packets:
                    self._send_packet_immediate(packet_data)
                
                # Small sleep to prevent busy-wait
                time.sleep(0.001)  # 1ms
            except Exception as e:
                print(f"⚠️  AB processing error: {e}")

    def start(self):
        if self.mode == 'listener':
            self.listener_socket = self._create_socket()
            addr = struct.pack('HH4sxxxxxxxx', AF_INET, socket.htons(self.port),
                             socket.inet_aton('0.0.0.0'))

            if libsrt.srt_bind(self.listener_socket, addr, len(addr)) < 0:
                print(f"✗ Failed to bind TX {self.port}")
                return False

            if libsrt.srt_listen(self.listener_socket, 100) < 0:
                print(f"✗ Failed to listen TX {self.port}")
                return False

            print(f"✓ TX {self.port} listening (route {self.route_id})")
            threading.Thread(target=self._accept_decoders, daemon=True).start()
            return True
            
        elif self.mode == 'caller':
            print(f"✓ TX {self.port} starting in caller mode to {self.host}:{self.remote_port}")
            threading.Thread(target=self._connect_caller, daemon=True).start()
            return True
            
        elif self.mode == 'rendezvous':
            print(f"✓ TX {self.port} starting in rendezvous mode with peer {self.host}:{self.remote_port}")
            threading.Thread(target=self._connect_rendezvous, daemon=True).start()
            return True

        return False
    
    def _connect_caller(self):
        """Connect to remote decoder in caller mode"""
        while self.running:
            try:
                sock = self._create_socket()
                
                # Bind to local port
                local_addr = struct.pack('HH4sxxxxxxxx', AF_INET, socket.htons(self.port),
                                       socket.inet_aton('0.0.0.0'))
                if libsrt.srt_bind(sock, local_addr, len(local_addr)) < 0:
                    print(f"✗ Failed to bind TX {self.port}")
                    libsrt.srt_close(sock)
                    time.sleep(5)
                    continue
                
                # Connect to remote decoder
                remote_port = self.remote_port if self.remote_port else self.port
                remote_addr = struct.pack('HH4sxxxxxxxx', AF_INET, socket.htons(remote_port),
                                        socket.inet_aton(self.host))
                
                if libsrt.srt_connect(sock, remote_addr, len(remote_addr)) < 0:
                    print(f"✗ Failed to connect TX {self.port} to {self.host}:{remote_port}")
                    libsrt.srt_close(sock)
                    time.sleep(5)
                    continue
                
                print(f"✓ TX {self.port} connected to decoder {self.host}:{remote_port}")
                
                with self.lock:
                    self.decoder_sockets.append(sock)
                
                # Keep connection alive - monitor for disconnection
                while self.running:
                    time.sleep(1)
                    # Check if socket is still valid (would disconnect on error)
                    if sock not in self.decoder_sockets:
                        break
                        
            except Exception as e:
                print(f"✗ TX {self.port} caller error: {e}")
                time.sleep(5)
    
    def _connect_rendezvous(self):
        """Connect to peer in rendezvous mode"""
        while self.running:
            try:
                sock = self._create_socket()
                
                # Enable rendezvous mode
                val = ctypes.c_int(1)
                libsrt.srt_setsockopt(sock, 0, SRTO_RENDEZVOUS, ctypes.byref(val), ctypes.sizeof(val))
                
                # Bind to local port
                local_addr = struct.pack('HH4sxxxxxxxx', AF_INET, socket.htons(self.port),
                                       socket.inet_aton('0.0.0.0'))
                if libsrt.srt_bind(sock, local_addr, len(local_addr)) < 0:
                    print(f"✗ Failed to bind TX {self.port}")
                    libsrt.srt_close(sock)
                    time.sleep(5)
                    continue
                
                # Connect to peer
                peer_port = self.remote_port if self.remote_port else self.port
                peer_addr = struct.pack('HH4sxxxxxxxx', AF_INET, socket.htons(peer_port),
                                      socket.inet_aton(self.host))
                
                if libsrt.srt_connect(sock, peer_addr, len(peer_addr)) < 0:
                    print(f"✗ Failed rendezvous TX {self.port} with peer {self.host}:{peer_port}")
                    libsrt.srt_close(sock)
                    time.sleep(5)
                    continue
                
                print(f"✓ TX {self.port} rendezvous connected to peer {self.host}:{peer_port}")
                
                with self.lock:
                    self.decoder_sockets.append(sock)
                
                # Keep connection alive
                while self.running:
                    time.sleep(1)
                    if sock not in self.decoder_sockets:
                        break
                        
            except Exception as e:
                print(f"✗ TX {self.port} rendezvous error: {e}")
                time.sleep(5)

    def _create_socket(self) -> int:
        sock = libsrt.srt_create_socket()

        val = ctypes.c_int(self.latency)
        libsrt.srt_setsockopt(sock, 0, SRTO_LATENCY, ctypes.byref(val), ctypes.sizeof(val))

        if self.buffer:
            val = ctypes.c_int(self.buffer)
            libsrt.srt_setsockopt(sock, 0, SRTO_SNDBUF, ctypes.byref(val), ctypes.sizeof(val))

        if self.passphrase:
            p = self.passphrase.encode('utf-8')
            libsrt.srt_setsockopt(sock, 0, SRTO_PASSPHRASE, p, len(p))
            klen = ctypes.c_int(32)
            libsrt.srt_setsockopt(sock, 0, SRTO_PBKEYLEN, ctypes.byref(klen), ctypes.sizeof(klen))
            print(f"  → TX Encryption enabled (AES-256)")

        # Apply Stream ID if provided
        if self.streamid:
            sid = self.streamid.encode('utf-8')
            libsrt.srt_setsockopt(sock, 0, SRTO_STREAMID, sid, len(sid))
            print(f"  → TX Stream ID set: '{self.streamid}'")

        # Apply Max Bandwidth if provided
        if self.maxbw and self.maxbw > 0:
            bw = ctypes.c_int64(self.maxbw)
            libsrt.srt_setsockopt(sock, 0, SRTO_MAXBW, ctypes.byref(bw), ctypes.sizeof(bw))
            print(f"  → TX Max Bandwidth set: {self.maxbw} bytes/sec")

        return sock

    def _accept_decoders(self):
        while self.running:
            addr_buf = ctypes.create_string_buffer(128)
            addrlen = ctypes.c_int(128)

            decoder_sock = libsrt.srt_accept(self.listener_socket, addr_buf, ctypes.byref(addrlen))

            if decoder_sock != SRT_INVALID_SOCK:
                with self.lock:
                    self.decoder_sockets.append(decoder_sock)
                print(f"✓ Decoder connected to TX {self.port} (total: {len(self.decoder_sockets)})")
            else:
                time.sleep(0.1)

    def send_packet(self, data: bytes) -> int:
        """Send packet (either through AB or directly)"""
        if self.adaptive_buffer.enabled:
            # Add to adaptive buffer (will be sent by background thread)
            self.adaptive_buffer.add_packet(data)
            return 1  # Assume success (actual sending happens async)
        else:
            # Direct send (original behavior)
            return self._send_packet_immediate(data)
    
    def _send_packet_immediate(self, data: bytes) -> int:
        """Send packet immediately to all connected decoders"""
        sent_count = 0
        dead_sockets = []

        with self.lock:
            for sock in self.decoder_sockets:
                result = libsrt.srt_send(sock, data, len(data))
                if result > 0:
                    self.bitrate.add(result)
                    self.packets_sent += 1
                    sent_count += 1
                elif result < 0:
                    dead_sockets.append(sock)

            for sock in dead_sockets:
                self.decoder_sockets.remove(sock)
                libsrt.srt_close(sock)
                print(f"✗ Decoder disconnected from TX {self.port}")

        return sent_count

    def get_client_count(self) -> int:
        with self.lock:
            return len(self.decoder_sockets)

    def get_stats(self) -> dict:
        packet_loss = 0.0
        if self.packets_sent > 0:
            packet_loss = (self.packets_lost / self.packets_sent) * 100

        # Get real stats from C extension (REQUIRED)
        real_stats = {}
        try:
            import srt_stats
            # Get stats from first connected socket
            with self.lock:
                if self.decoder_sockets:
                    sock = self.decoder_sockets[0]
                    real_stats = srt_stats.get_stats(sock, 0)  # Don't clear stats
                else:
                    # No clients connected yet
                    real_stats = {}
        except ImportError as e:
            # C extension not available - CRITICAL ERROR
            if not hasattr(self, '_warned_no_stats'):
                print(f"❌ CRITICAL: srt_stats C extension not available for TX {self.port}")
                print(f"   Error: {e}")
                print(f"   Statistics and Adaptive Buffer DISABLED!")
                print(f"   Fix: cd /opt/srt-gateway/srt_stats_extension && sudo ./build.sh")
                self._warned_no_stats = True
            # Return empty stats instead of None
            return {
                'rtt': 0.0,
                'packet_loss': 0.0,
                'packets_sent': self.packets_sent
            }
        except Exception as e:
            # Socket error or other issue - log and use empty stats
            if not hasattr(self, '_warned_socket_error'):
                print(f"⚠️  Warning: Cannot get stats from socket on TX {self.port}: {e}")
                self._warned_socket_error = True
            real_stats = {}
        
        # Update AB with stats
        if self.adaptive_buffer.enabled and real_stats:
            self.adaptive_buffer.update_health(real_stats)
        
        # Extract RTT
        if 'msRTT' in real_stats:
            self.rtt = real_stats['msRTT']
        
        # Add RTT to history
        self.rtt_history.add(self.rtt)

        stats_dict = {
            'rtt': round(self.rtt, 2),
            'packet_loss': round(packet_loss, 3),
            'packets_sent': self.packets_sent,
            'effective_latency': round(self.rtt, 2)  # Real-time network latency (RTT)
        }
        
        # Add AB stats if enabled
        if self.adaptive_buffer.enabled:
            ab_stats = self.adaptive_buffer.get_stats()
            # Calculate total effective latency: Real RTT + AB software buffer
            total_latency = round(self.rtt + ab_stats['current_latency_ms'], 2)
            stats_dict['adaptive_buffer'] = ab_stats
            stats_dict['adaptive_buffer']['total_latency_ms'] = total_latency
            stats_dict['effective_latency'] = total_latency  # Override with RTT + buffer
        
        return stats_dict

    def stop(self):
        self.running = False
        with self.lock:
            for sock in self.decoder_sockets:
                libsrt.srt_close(sock)
            self.decoder_sockets.clear()

        if self.listener_socket != SRT_INVALID_SOCK:
            libsrt.srt_close(self.listener_socket)

class Session:
    def __init__(self, session_id: int, name: str, rx_port: int, rx_mode: str,
                 rx_host: str, rx_remote_port: Optional[int], rx_streamid: Optional[str],
                 rx_maxbw: int, latency: int, buffer: int, passphrase: Optional[str]):
        self.session_id = session_id
        self.name = name
        self.rx_port = rx_port
        self.rx_mode = rx_mode
        self.rx_host = rx_host
        self.rx_remote_port = rx_remote_port
        self.rx_streamid = rx_streamid
        self.rx_maxbw = rx_maxbw
        self.latency = latency
        self.buffer = buffer
        self.passphrase = passphrase

        self.rx_bitrate = BitrateCalculator()
        self.rx_bitrate_history = HistoricalDataBuffer(300)  # Last 5 minutes
        self.rx_rtt_history = HistoricalDataBuffer(300)  # Track RX RTT
        self.tx_outputs: Dict[int, TXOutput] = {}
        self.has_input = False
        self.running = True
        self.start_time = time.time()
        self.listener_socket = -1
        self.rx_sock = -1
        self.rx_packets_received = 0
        self.rx_packets_history = HistoricalDataBuffer(300)
        self.rx_rtt = 0.0  # Actual measured RTT

    def add_tx_output(self, tx: TXOutput):
        self.tx_outputs[tx.route_id] = tx
        tx.start()

    def remove_tx_output(self, route_id: int):
        if route_id in self.tx_outputs:
            self.tx_outputs[route_id].stop()
            del self.tx_outputs[route_id]

    def run(self):
        rx_sock = libsrt.srt_create_socket()

        val = ctypes.c_int(self.latency)
        libsrt.srt_setsockopt(rx_sock, 0, SRTO_LATENCY, ctypes.byref(val), ctypes.sizeof(val))

        if self.buffer:
            val = ctypes.c_int(self.buffer)
            libsrt.srt_setsockopt(rx_sock, 0, SRTO_RCVBUF, ctypes.byref(val), ctypes.sizeof(val))

        if self.passphrase:
            p = self.passphrase.encode('utf-8')
            libsrt.srt_setsockopt(rx_sock, 0, SRTO_PASSPHRASE, p, len(p))
            klen = ctypes.c_int(32)
            libsrt.srt_setsockopt(rx_sock, 0, SRTO_PBKEYLEN, ctypes.byref(klen), ctypes.sizeof(klen))
            print(f"  → RX Encryption enabled (AES-256)")

        # Apply Stream ID if provided
        if self.rx_streamid:
            sid = self.rx_streamid.encode('utf-8')
            libsrt.srt_setsockopt(rx_sock, 0, SRTO_STREAMID, sid, len(sid))
            print(f"  → RX Stream ID set: '{self.rx_streamid}'")

        # Apply Max Bandwidth if provided
        if self.rx_maxbw and self.rx_maxbw > 0:
            bw = ctypes.c_int64(self.rx_maxbw)
            libsrt.srt_setsockopt(rx_sock, 0, SRTO_MAXBW, ctypes.byref(bw), ctypes.sizeof(bw))
            print(f"  → RX Max Bandwidth set: {self.rx_maxbw} bytes/sec")

        if self.rx_mode == 'listener':
            addr = struct.pack('HH4sxxxxxxxx', AF_INET, socket.htons(self.rx_port),
                             socket.inet_aton('0.0.0.0'))

            if libsrt.srt_bind(rx_sock, addr, len(addr)) < 0:
                print(f"✗ Failed to bind RX {self.rx_port}")
                return

            if libsrt.srt_listen(rx_sock, 1) < 0:
                print(f"✗ Failed to listen RX {self.rx_port}")
                return

            print(f"✓ RX {self.rx_port} listening - {self.name}")

        elif self.rx_mode == 'caller':
            # Bind to local port first
            local_addr = struct.pack('HH4sxxxxxxxx', AF_INET, socket.htons(self.rx_port),
                                   socket.inet_aton('0.0.0.0'))
            if libsrt.srt_bind(rx_sock, local_addr, len(local_addr)) < 0:
                print(f"✗ Failed to bind RX {self.rx_port}")
                return

            # Connect to remote encoder
            remote_port = self.rx_remote_port if self.rx_remote_port else self.rx_port
            remote_addr = struct.pack('HH4sxxxxxxxx', AF_INET, socket.htons(remote_port),
                                    socket.inet_aton(self.rx_host))
            
            print(f"✓ RX {self.rx_port} connecting to {self.rx_host}:{remote_port} (caller) - {self.name}")
            
        elif self.rx_mode == 'rendezvous':
            # Enable rendezvous mode
            val = ctypes.c_int(1)
            libsrt.srt_setsockopt(rx_sock, 0, SRTO_RENDEZVOUS, ctypes.byref(val), ctypes.sizeof(val))
            
            # Bind to local port
            local_addr = struct.pack('HH4sxxxxxxxx', AF_INET, socket.htons(self.rx_port),
                                   socket.inet_aton('0.0.0.0'))
            if libsrt.srt_bind(rx_sock, local_addr, len(local_addr)) < 0:
                print(f"✗ Failed to bind RX {self.rx_port}")
                return

            print(f"✓ RX {self.rx_port} rendezvous mode to peer {self.rx_host}:{self.rx_remote_port} - {self.name}")

        while self.running:
            encoder_sock = SRT_INVALID_SOCK
            
            if self.rx_mode == 'listener':
                addr_buf = ctypes.create_string_buffer(128)
                addrlen = ctypes.c_int(128)
                encoder_sock = libsrt.srt_accept(rx_sock, addr_buf, ctypes.byref(addrlen))

                if encoder_sock == SRT_INVALID_SOCK:
                    continue

                print(f"✓ Encoder connected to RX {self.rx_port}")
                
            elif self.rx_mode == 'caller':
                remote_port = self.rx_remote_port if self.rx_remote_port else self.rx_port
                remote_addr = struct.pack('HH4sxxxxxxxx', AF_INET, socket.htons(remote_port),
                                        socket.inet_aton(self.rx_host))
                
                encoder_sock = rx_sock
                if libsrt.srt_connect(encoder_sock, remote_addr, len(remote_addr)) < 0:
                    print(f"✗ Failed to connect RX {self.rx_port} to {self.rx_host}:{remote_port}")
                    time.sleep(5)
                    continue
                    
                print(f"✓ RX {self.rx_port} connected to encoder {self.rx_host}:{remote_port}")
                
            elif self.rx_mode == 'rendezvous':
                peer_port = self.rx_remote_port if self.rx_remote_port else self.rx_port
                peer_addr = struct.pack('HH4sxxxxxxxx', AF_INET, socket.htons(peer_port),
                                      socket.inet_aton(self.rx_host))
                
                encoder_sock = rx_sock
                if libsrt.srt_connect(encoder_sock, peer_addr, len(peer_addr)) < 0:
                    print(f"✗ Failed rendezvous RX {self.rx_port} with peer {self.rx_host}:{peer_port}")
                    time.sleep(5)
                    continue
                    
                print(f"✓ RX {self.rx_port} rendezvous connected to peer {self.rx_host}:{peer_port}")

            self.has_input = True

            buf = ctypes.create_string_buffer(1500)
            while self.running:
                result = libsrt.srt_recv(encoder_sock, buf, 1500)
                if result <= 0:
                    break

                self.rx_bitrate.add(result)
                self.rx_packets_received += 1
                data = buf.raw[:result]

                for tx in self.tx_outputs.values():
                    tx.send_packet(data)

            self.has_input = False
            
            if self.rx_mode == 'listener':
                libsrt.srt_close(encoder_sock)
                print(f"✗ Encoder disconnected from RX {self.rx_port}")
            else:
                print(f"✗ RX {self.rx_port} disconnected, reconnecting...")
                time.sleep(2)

        libsrt.srt_close(rx_sock)

    def stop(self):
        print(f"✓ Stopping session {self.rx_port}")
        self.running = False
        for tx in self.tx_outputs.values():
            tx.stop()

    def get_stats(self) -> dict:
        # Calculate current bitrate and update history
        current_rx_bitrate = self.rx_bitrate.calculate()
        self.rx_bitrate_history.add(current_rx_bitrate)
        self.rx_packets_history.add(self.rx_packets_received)
        
        # Calculate average RTT from all TX outputs (approximate RX RTT)
        if self.tx_outputs:
            total_rtt = sum(tx.rtt for tx in self.tx_outputs.values())
            self.rx_rtt = total_rtt / len(self.tx_outputs)
        else:
            # Use configured latency as fallback when no outputs
            self.rx_rtt = float(self.latency)
        
        self.rx_rtt_history.add(self.rx_rtt)
        
        tx_stats = {}
        for route_id, tx in self.tx_outputs.items():
            stats = tx.get_stats()
            # Update TX historical data
            current_tx_bitrate = tx.bitrate.calculate()
            tx.bitrate_history.add(current_tx_bitrate)
            tx.packets_sent_history.add(tx.packets_sent)
            
            tx_stat = {
                'port': tx.port,
                'clients': tx.get_client_count(),
                'tx_bitrate': current_tx_bitrate,
                'tx_bitrate_history': tx.bitrate_history.get_with_timestamps(),
                'rtt': stats['rtt'],
                'rtt_history': tx.rtt_history.get_with_timestamps(),
                'packet_loss': stats['packet_loss'],
                'packets_sent': stats['packets_sent'],
                'packets_sent_history': tx.packets_sent_history.get_with_timestamps(),
                'effective_latency': stats.get('effective_latency', tx.latency)  # Real latency (static or dynamic)
            }
            
            # Add AB stats if enabled
            if stats and 'adaptive_buffer' in stats:
                ab_stats = stats['adaptive_buffer']
                tx_stat['ab_enabled'] = ab_stats.get('enabled', False)
                tx_stat['ab_health_score'] = ab_stats.get('health_score', 0)
                tx_stat['ab_mode'] = ab_stats.get('mode', 'PASS_THROUGH')
                # Use total latency (SRT + buffer) instead of just buffer
                tx_stat['ab_current_latency'] = ab_stats.get('total_latency_ms', tx.latency)
            
            tx_stats[route_id] = tx_stat

        return {
            'name': self.name,
            'rx_port': self.rx_port,
            'rx_mode': self.rx_mode,
            'has_input': self.has_input,
            'rx_bitrate': current_rx_bitrate,
            'rx_bitrate_history': self.rx_bitrate_history.get_with_timestamps(),
            'rx_packets_received': self.rx_packets_received,
            'rx_packets_history': self.rx_packets_history.get_with_timestamps(),
            'rx_rtt': self.rx_rtt,  # Actual measured RTT
            'rx_rtt_history': self.rx_rtt_history.get_with_timestamps(),
            'latency': self.latency,  # Configured latency
            'uptime': int(time.time() - self.start_time),
            'tx_outputs': tx_stats
        }

class Gateway:
    def __init__(self):
        self.sessions: Dict[int, Session] = {}
        self.running = False
        self.db_path = '/opt/srt-gateway/gateway.db'
        self.lock = threading.Lock()

    def load_session(self, rx_port: int):
        """Load a single specific session - HOT RELOAD"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM sessions WHERE rx_port = ? AND status = "running"', (rx_port,))
        sess_data = cursor.fetchone()

        if not sess_data:
            conn.close()
            return

        sess_data = dict(sess_data)

        with self.lock:
            # Don't reload if already running
            if rx_port in self.sessions:
                print(f"⚠️  Session {rx_port} already running")
                conn.close()
                return

            session = Session(
                sess_data['rx_port'],
                sess_data['name'],
                sess_data['rx_port'],
                sess_data['rx_mode'],
                sess_data['rx_host'],
                sess_data.get('rx_remote_port'),
                sess_data.get('rx_streamid'),
                sess_data.get('rx_maxbw', 0),
                sess_data['latency'],
                sess_data['buffer_size'],
                sess_data['passphrase']
            )

            cursor.execute('SELECT * FROM routes WHERE session_rx_port = ? AND status = "running"',
                         (rx_port,))
            routes = [dict(r) for r in cursor.fetchall()]

            for route in routes:
                tx = TXOutput(
                    route['id'],
                    route['tx_port'],
                    route['tx_mode'],
                    route['tx_host'],
                    route.get('tx_remote_port'),
                    route.get('tx_streamid'),
                    route.get('tx_maxbw'),
                    route.get('latency', sess_data['latency']),
                    route.get('passphrase', sess_data['passphrase']),
                    route.get('buffer_size', sess_data['buffer_size']),
                    adaptive_buffer_enabled=bool(route.get('adaptive_buffer_enabled', 0)),
                    ab_weight_loss=route.get('ab_weight_loss', 40),
                    ab_weight_buffer=route.get('ab_weight_buffer', 30),
                    ab_weight_jitter=route.get('ab_weight_jitter', 20),
                    ab_weight_rtt=route.get('ab_weight_rtt', 10),
                    ab_max_buffer_ms=route.get('ab_max_buffer_ms', 2000)
                )
                session.add_tx_output(tx)

            self.sessions[rx_port] = session
            threading.Thread(target=session.run, daemon=True).start()
            print(f"✓ HOT RELOAD: Started session {rx_port} - {sess_data['name']}")

        conn.close()

    def remove_session(self, rx_port: int):
        """Remove a single specific session - HOT REMOVE"""
        with self.lock:
            if rx_port in self.sessions:
                self.sessions[rx_port].stop()
                del self.sessions[rx_port]
                print(f"✓ HOT REMOVE: Stopped session {rx_port}")
            else:
                print(f"⚠️  Session {rx_port} not running")

    def load_all_sessions(self):
        """Initial load of all sessions"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT rx_port FROM sessions WHERE status = "running"')
        rx_ports = [row['rx_port'] for row in cursor.fetchall()]
        conn.close()

        for rx_port in rx_ports:
            self.load_session(rx_port)

        print(f"✓ Initial load: {len(self.sessions)} sessions")

    def export_stats(self):
        while self.running:
            with self.lock:
                stats = {
                    'timestamp': int(time.time()),
                    'sessions': {
                        rx_port: session.get_stats()
                        for rx_port, session in self.sessions.items()
                    }
                }

            with open('/tmp/srt-gateway-stats.json', 'w') as f:
                json.dump(stats, f)

            time.sleep(1)

    def monitor_signals(self):
        """Monitor for hot reload signals"""
        while self.running:
            # HOT ADD - add new session without touching others
            for sig in glob.glob('/tmp/srt-add-*.signal'):
                try:
                    rx_port = int(sig.split('-')[2].replace('.signal', ''))
                    print(f"📡 Signal: Add session {rx_port}")
                    self.load_session(rx_port)
                    os.remove(sig)
                except Exception as e:
                    print(f"Error adding session: {e}")
                    try:
                        os.remove(sig)
                    except:
                        pass

            # HOT REMOVE - remove session without touching others
            for sig in glob.glob('/tmp/srt-remove-*.signal'):
                try:
                    rx_port = int(sig.split('-')[2].replace('.signal', ''))
                    print(f"📡 Signal: Remove session {rx_port}")
                    self.remove_session(rx_port)
                    os.remove(sig)
                except Exception as e:
                    print(f"Error removing session: {e}")
                    try:
                        os.remove(sig)
                    except:
                        pass

            time.sleep(0.5)

    def run(self):
        libsrt.srt_startup()
        self.running = True

        print("🚀 SRT Gateway with HOT RELOAD starting...")
        self.load_all_sessions()

        threading.Thread(target=self.export_stats, daemon=True).start()
        threading.Thread(target=self.monitor_signals, daemon=True).start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            self.running = False
            with self.lock:
                for session in self.sessions.values():
                    session.stop()
            libsrt.srt_cleanup()

if __name__ == "__main__":
    Gateway().run()
