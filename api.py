#!/usr/bin/env python3
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import sqlite3
import json
import time
import os
import asyncio
from typing import List

app = FastAPI(title="SRT Gateway v6.0")

# Mount static files directory
app.mount("/static", StaticFiles(directory="/opt/srt-gateway/static"), name="static")

DB_PATH = '/opt/srt-gateway/gateway.db'
STATS_FILE = '/tmp/srt_stats.json'

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def read_root():
    return FileResponse("/opt/srt-gateway/static/index.html")

@app.get("/favicon.ico")
def favicon():
    """Return a simple SVG favicon to prevent 404 errors"""
    from fastapi.responses import Response
    svg_favicon = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" fill="#ff6b35"/>
        <text x="50" y="70" font-size="60" font-weight="bold" text-anchor="middle" fill="white">S</text>
    </svg>'''
    return Response(content=svg_favicon, media_type="image/svg+xml")

@app.get("/api/sessions")
def get_sessions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions ORDER BY created_at DESC')
    sessions = [dict(row) for row in cursor.fetchall()]
    
    for session in sessions:
        cursor.execute('SELECT * FROM routes WHERE session_rx_port = ? ORDER BY id', (session['rx_port'],))
        session['routes'] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    # Merge real-time stats from srt_router
    try:
        import json
        with open("/tmp/srt-gateway-stats.json", "r") as sf:
            stats = json.load(sf)
        
        for session in sessions:
            port_key = str(session["rx_port"])
            if port_key in stats.get("sessions", {}):
                session_stats = stats["sessions"][port_key]
                session["has_input"] = session_stats.get("has_input", False)
                session["rx_bitrate"] = session_stats.get("rx_bitrate", 0)
                session["rx_rtt"] = session_stats.get("rx_rtt", 0)
                session["uptime"] = session_stats.get("uptime", 0)
                
                # Merge route stats
                tx_outputs = session_stats.get("tx_outputs", {})
                for route in session.get("routes", []):
                    route_key = str(route["id"])
                    if route_key in tx_outputs:
                        route_stats = tx_outputs[route_key]
                        route["clients"] = route_stats.get("clients", 0)
                        route["tx_bitrate"] = route_stats.get("tx_bitrate", 0)
                        route["rtt"] = route_stats.get("rtt", 0)
                        route["packet_loss"] = route_stats.get("packet_loss", 0)
                        route["effective_latency"] = route_stats.get("effective_latency", route["latency"])
                        
                        # Add AB stats
                        if route.get("adaptive_buffer_enabled"):
                            route["ab_health_score"] = route_stats.get("ab_health_score", 0)
                            route["ab_mode"] = route_stats.get("ab_mode", "PASS_THROUGH")
                            route["ab_current_latency"] = route_stats.get("ab_current_latency", 35)
    except Exception as e:
        pass  # If stats file doesn't exist yet, continue without stats
    
    return {"ok": True, "sessions": sessions}

@app.get("/api/sessions/{rx_port}")
def get_session(rx_port: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions WHERE rx_port = ?', (rx_port,))
    session = cursor.fetchone()
    
    if not session:
        conn.close()
        raise HTTPException(404, "Session not found")
    
    session_dict = dict(session)
    cursor.execute('SELECT * FROM routes WHERE session_rx_port = ? ORDER BY id', (rx_port,))
    session_dict['routes'] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return session_dict

@app.get("/api/stats/history/{rx_port}")
def get_stats_history(rx_port: int, limit: int = 300):
    """Get historical metrics data for a session with timestamps"""
    try:
        with open("/tmp/srt-gateway-stats.json", "r") as sf:
            stats = json.load(sf)
        
        port_key = str(rx_port)
        if port_key not in stats.get("sessions", {}):
            raise HTTPException(404, "Session not found or not active")
        
        session_stats = stats["sessions"][port_key]
        
        # Apply limit to historical data
        def limit_history(hist_data):
            if isinstance(hist_data, dict) and 'values' in hist_data and 'timestamps' in hist_data:
                return {
                    'values': hist_data['values'][-limit:],
                    'timestamps': hist_data['timestamps'][-limit:]
                }
            return hist_data
        
        response = {
            'ok': True,
            'rx_port': rx_port,
            'name': session_stats.get('name'),
            'rx_mode': session_stats.get('rx_mode'),
            'rx_bitrate': session_stats.get('rx_bitrate', 0),
            'rx_bitrate_history': limit_history(session_stats.get('rx_bitrate_history', {'values': [], 'timestamps': []})),
            'rx_rtt': session_stats.get('rx_rtt', 0),
            'rx_rtt_history': limit_history(session_stats.get('rx_rtt_history', {'values': [], 'timestamps': []})),
            'rx_packets_history': limit_history(session_stats.get('rx_packets_history', {'values': [], 'timestamps': []})),
            'uptime': session_stats.get('uptime', 0),
            'routes': []
        }
        
        # Include per-route history as array
        tx_outputs = session_stats.get('tx_outputs', {})
        for route_id, route_stats in tx_outputs.items():
            response['routes'].append({
                'route_id': route_id,
                'port': route_stats.get('port'),
                'clients': route_stats.get('clients', 0),
                'tx_bitrate': route_stats.get('tx_bitrate', 0),
                'tx_bitrate_history': limit_history(route_stats.get('tx_bitrate_history', {'values': [], 'timestamps': []})),
                'rtt': route_stats.get('rtt', 0),
                'rtt_history': limit_history(route_stats.get('rtt_history', {'values': [], 'timestamps': []})),
                'packet_loss': route_stats.get('packet_loss', 0),
                'packets_sent_history': limit_history(route_stats.get('packets_sent_history', {'values': [], 'timestamps': []}))
            })
        
        return response
        
    except FileNotFoundError:
        raise HTTPException(503, "Stats not available yet")
    except Exception as e:
        raise HTTPException(500, f"Error loading stats: {str(e)}")

@app.post("/api/sessions")
async def create_session(request: Request):
    data = await request.json()
    
    name = data.get('name')
    rx_port = int(data.get('rx_port'))
    rx_mode = data.get('rx_mode', 'listener')
    rx_host = data.get('rx_host', '0.0.0.0')
    rx_remote_port = data.get('rx_remote_port')
    rx_streamid = data.get('rx_streamid')
    rx_maxbw = int(data.get('rx_maxbw', 0))
    latency = int(data.get('latency', 200))
    buffer_size = int(data.get('buffer_size', 8192))
    passphrase = data.get('passphrase')
    routes = data.get('routes', [])
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT rx_port FROM sessions WHERE rx_port = ?', (rx_port,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(400, "Port already in use")
        
        cursor.execute('''
            INSERT INTO sessions (name, rx_port, rx_mode, rx_host, rx_remote_port, rx_streamid, rx_maxbw, latency, buffer_size, passphrase, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, rx_port, rx_mode, rx_host, rx_remote_port, rx_streamid, rx_maxbw, latency, buffer_size, passphrase, 'running'))
        
        for route in routes:
            # Extract AB parameters
            adaptive_buffer_enabled = int(route.get('adaptive_buffer_enabled', 0))
            ab_weight_loss = int(route.get('ab_weight_loss', 40))
            ab_weight_buffer = int(route.get('ab_weight_buffer', 30))
            ab_weight_jitter = int(route.get('ab_weight_jitter', 20))
            ab_weight_rtt = int(route.get('ab_weight_rtt', 10))
            ab_max_buffer_ms = int(route.get('ab_max_buffer_ms', 2000))
            
            cursor.execute('''
                INSERT INTO routes (session_rx_port, tx_port, tx_mode, tx_host, tx_remote_port, tx_streamid, tx_maxbw, latency, buffer_size, passphrase, status, adaptive_buffer_enabled, ab_weight_loss, ab_weight_buffer, ab_weight_jitter, ab_weight_rtt, ab_max_buffer_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rx_port,
                int(route.get('tx_port')),
                route.get('tx_mode', 'listener'),
                route.get('tx_host', '0.0.0.0'),
                int(route.get('tx_remote_port')) if route.get('tx_remote_port') else None,
                route.get('tx_streamid'),
                int(route.get('tx_maxbw', 0)),
                int(route.get('latency', 120)),
                int(route.get('buffer_size', 12000000)),
                route.get('passphrase'),
                'running',
                adaptive_buffer_enabled,
                ab_weight_loss,
                ab_weight_buffer,
                ab_weight_jitter,
                ab_weight_rtt,
                ab_max_buffer_ms
            ))
        
        conn.commit()
        
        # Signal router to start session
        with open(f'/tmp/srt-add-{rx_port}.signal', 'w') as f:
            f.write(str(rx_port))
        
        return {"ok": True, "message": "Session created"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.put("/api/sessions/{rx_port}")
async def update_session(rx_port: int, request: Request):
    data = await request.json()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM sessions WHERE rx_port = ?', (rx_port,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(404, "Session not found")
        
        updates = []
        params = []
        
        if 'name' in data:
            updates.append('name = ?')
            params.append(data['name'])
        if 'rx_mode' in data:
            updates.append('rx_mode = ?')
            params.append(data['rx_mode'])
        if 'rx_host' in data:
            updates.append('rx_host = ?')
            params.append(data['rx_host'])
        if 'rx_remote_port' in data:
            updates.append('rx_remote_port = ?')
            params.append(data['rx_remote_port'])
        if 'rx_streamid' in data:
            updates.append('rx_streamid = ?')
            params.append(data['rx_streamid'])
        if 'rx_maxbw' in data:
            updates.append('rx_maxbw = ?')
            params.append(int(data['rx_maxbw']))
        if 'latency' in data:
            updates.append('latency = ?')
            params.append(int(data['latency']))
        if 'buffer_size' in data:
            updates.append('buffer_size = ?')
            params.append(int(data['buffer_size']))
        if data.get('passphrase'):
            updates.append('passphrase = ?')
            params.append(data['passphrase'])
        
        if updates:
            params.append(rx_port)
            query = f"UPDATE sessions SET {', '.join(updates)} WHERE rx_port = ?"
            cursor.execute(query, params)
            conn.commit()
        
        # Hot reload: signal remove then add
        with open(f'/tmp/srt-remove-{rx_port}.signal', 'w') as f:
            f.write(str(rx_port))
        
        await asyncio.sleep(0.5)
        
        with open(f'/tmp/srt-add-{rx_port}.signal', 'w') as f:
            f.write(str(rx_port))
        
        return {"ok": True, "message": "Session updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.delete("/api/sessions/{rx_port}")
def delete_session(rx_port: int):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM routes WHERE session_rx_port = ?', (rx_port,))
        cursor.execute('DELETE FROM sessions WHERE rx_port = ?', (rx_port,))
        conn.commit()
        
        # Signal router to stop session
        with open(f'/tmp/srt-remove-{rx_port}.signal', 'w') as f:
            f.write(str(rx_port))
        
        return {"ok": True, "message": "Session deleted"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.post("/api/sessions/{rx_port}/stop")
async def stop_session(rx_port: int):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE sessions SET status = ? WHERE rx_port = ?', ('stopped', rx_port))
        cursor.execute('UPDATE routes SET status = ? WHERE session_rx_port = ?', ('stopped', rx_port))
        conn.commit()
        
        # Signal router to stop session
        with open(f'/tmp/srt-remove-{rx_port}.signal', 'w') as f:
            f.write(str(rx_port))
        
        return {"ok": True, "message": "Session stopped"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.post("/api/sessions/{rx_port}/start")
async def start_session(rx_port: int):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE sessions SET status = ? WHERE rx_port = ?', ('running', rx_port))
        cursor.execute('UPDATE routes SET status = ? WHERE session_rx_port = ?', ('running', rx_port))
        conn.commit()
        
        await asyncio.sleep(0.5)
        
        # Signal router to start session
        with open(f'/tmp/srt-add-{rx_port}.signal', 'w') as f:
            f.write(str(rx_port))
        
        return {"ok": True, "message": "Session started"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.get("/api/routes/{route_id}")
def get_route(route_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM routes WHERE id = ?', (route_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Route not found")
    return dict(row)

@app.post("/api/routes")
async def add_route(request: Request):
    data = await request.json()
    
    session_rx_port = int(data.get('session_rx_port'))
    tx_port = int(data.get('tx_port'))
    tx_mode = data.get('tx_mode', 'listener')
    tx_host = data.get('tx_host', '0.0.0.0')
    tx_remote_port = data.get('tx_remote_port')
    tx_streamid = data.get('tx_streamid')
    tx_maxbw = int(data.get('tx_maxbw', 0))
    latency = int(data.get('latency', 120))
    buffer_size = int(data.get('buffer_size', 12000000))
    passphrase = data.get('passphrase')
    
    # Adaptive Buffer parameters
    adaptive_buffer_enabled = int(data.get('adaptive_buffer_enabled', 0))
    ab_weight_loss = int(data.get('ab_weight_loss', 40))
    ab_weight_buffer = int(data.get('ab_weight_buffer', 30))
    ab_weight_jitter = int(data.get('ab_weight_jitter', 20))
    ab_weight_rtt = int(data.get('ab_weight_rtt', 10))
    ab_max_buffer_ms = int(data.get('ab_max_buffer_ms', 2000))
    
    # Validate weights sum to 100
    total_weight = ab_weight_loss + ab_weight_buffer + ab_weight_jitter + ab_weight_rtt
    if adaptive_buffer_enabled and total_weight != 100:
        raise HTTPException(400, f"Adaptive Buffer weights must sum to 100 (got {total_weight})")
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT rx_port FROM sessions WHERE rx_port = ?', (session_rx_port,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(404, "Session not found")
        
        cursor.execute('''
            INSERT INTO routes (session_rx_port, tx_port, tx_mode, tx_host, tx_remote_port, tx_streamid, tx_maxbw, latency, buffer_size, passphrase, status, adaptive_buffer_enabled, ab_weight_loss, ab_weight_buffer, ab_weight_jitter, ab_weight_rtt, ab_max_buffer_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_rx_port, tx_port, tx_mode, tx_host, tx_remote_port, tx_streamid, tx_maxbw, latency, buffer_size, passphrase, 'running', adaptive_buffer_enabled, ab_weight_loss, ab_weight_buffer, ab_weight_jitter, ab_weight_rtt, ab_max_buffer_ms))
        
        conn.commit()
        
        # Hot reload session to pick up new route
        with open(f'/tmp/srt-remove-{session_rx_port}.signal', 'w') as f:
            f.write(str(session_rx_port))
        
        await asyncio.sleep(0.5)
        
        with open(f'/tmp/srt-add-{session_rx_port}.signal', 'w') as f:
            f.write(str(session_rx_port))
        
        return {"ok": True, "message": "Route added"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.put("/api/routes/{route_id}")
async def update_route(route_id: int, request: Request):
    data = await request.json()
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT session_rx_port FROM routes WHERE id = ?', (route_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "Route not found")
        
        session_rx_port = row['session_rx_port']
        
        updates = []
        params = []
        
        if 'tx_port' in data:
            updates.append('tx_port = ?')
            params.append(int(data['tx_port']))
        if 'tx_mode' in data:
            updates.append('tx_mode = ?')
            params.append(data['tx_mode'])
        if 'tx_host' in data:
            updates.append('tx_host = ?')
            params.append(data['tx_host'])
        if 'tx_remote_port' in data:
            updates.append('tx_remote_port = ?')
            params.append(data['tx_remote_port'])
        if 'latency' in data:
            updates.append('latency = ?')
            params.append(int(data['latency']))
        if 'buffer_size' in data:
            updates.append('buffer_size = ?')
            params.append(int(data['buffer_size']))
        if 'tx_maxbw' in data:
            updates.append('tx_maxbw = ?')
            params.append(int(data['tx_maxbw']))
        if 'tx_streamid' in data:
            updates.append('tx_streamid = ?')
            params.append(data['tx_streamid'])
        if data.get('passphrase'):
            updates.append('passphrase = ?')
            params.append(data['passphrase'])
        
        # Adaptive Buffer parameters
        if 'adaptive_buffer_enabled' in data:
            updates.append('adaptive_buffer_enabled = ?')
            params.append(int(data['adaptive_buffer_enabled']))
        if 'ab_weight_loss' in data:
            updates.append('ab_weight_loss = ?')
            params.append(int(data['ab_weight_loss']))
        if 'ab_weight_buffer' in data:
            updates.append('ab_weight_buffer = ?')
            params.append(int(data['ab_weight_buffer']))
        if 'ab_weight_jitter' in data:
            updates.append('ab_weight_jitter = ?')
            params.append(int(data['ab_weight_jitter']))
        if 'ab_weight_rtt' in data:
            updates.append('ab_weight_rtt = ?')
            params.append(int(data['ab_weight_rtt']))
        if 'ab_max_buffer_ms' in data:
            updates.append('ab_max_buffer_ms = ?')
            params.append(int(data['ab_max_buffer_ms']))
        
        # Validate weights if AB is enabled
        if data.get('adaptive_buffer_enabled'):
            ab_loss = int(data.get('ab_weight_loss', 40))
            ab_buffer = int(data.get('ab_weight_buffer', 30))
            ab_jitter = int(data.get('ab_weight_jitter', 20))
            ab_rtt = int(data.get('ab_weight_rtt', 10))
            total_weight = ab_loss + ab_buffer + ab_jitter + ab_rtt
            if total_weight != 100:
                conn.close()
                raise HTTPException(400, f"Adaptive Buffer weights must sum to 100 (got {total_weight})")
        
        if updates:
            params.append(route_id)
            query = f"UPDATE routes SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
        
        # Hot reload session
        with open(f'/tmp/srt-remove-{session_rx_port}.signal', 'w') as f:
            f.write(str(session_rx_port))
        
        await asyncio.sleep(0.5)
        
        with open(f'/tmp/srt-add-{session_rx_port}.signal', 'w') as f:
            f.write(str(session_rx_port))
        
        return {"ok": True, "message": "Route updated"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.post("/api/routes/{route_id}/stop")
def delete_route(route_id: int):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT session_rx_port FROM routes WHERE id = ?', (route_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "Route not found")
        
        session_rx_port = row['session_rx_port']
        
        cursor.execute('DELETE FROM routes WHERE id = ?', (route_id,))
        conn.commit()
        
        # Hot reload session
        with open(f'/tmp/srt-remove-{session_rx_port}.signal', 'w') as f:
            f.write(str(session_rx_port))
        
        time.sleep(0.5)
        
        with open(f'/tmp/srt-add-{session_rx_port}.signal', 'w') as f:
            f.write(str(session_rx_port))
        
        return {"ok": True, "message": "Route deleted"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()

@app.get("/api/stats")
def get_stats():
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                stats = json.load(f)
            return stats
        return {"sessions": {}}
    except:
        return {"sessions": {}}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Send stats every 2 seconds
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, 'r') as f:
                    stats = f.read()
                await websocket.send_text(stats)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
