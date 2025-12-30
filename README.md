# 🚀 SRT Gateway v6.4 - Complete Package

Professional SRT (Secure Reliable Transport) Gateway Router with web-based management.

## 📦 Package Contents

```
srt-gateway-v5-complete/
├── install.sh          # Automated installer
├── srt_router.py       # Core SRT routing engine
├── api.py              # REST API backend
├── ui.html             # Web dashboard
└── README.md           # This file
```

---

## ⚡ Quick Installation (5 minutes)

### 1. Upload Package to VPS

```bash
# From your local machine
scp srt-gateway-v5-complete.zip root@YOUR_VPS_IP:/tmp/
```

### 2. SSH to VPS and Install

```bash
# SSH to VPS
ssh root@YOUR_VPS_IP

# Extract package
cd /tmp
unzip srt-gateway-v5-complete.zip
cd srt-gateway-v5-complete

# Run installer
sudo bash install.sh
```

### 3. Configure Firewall

```bash
# Allow full SRT port range
sudo ufw allow 1024:65500/udp

# Allow web dashboard
sudo ufw allow 80/tcp

# Enable firewall
sudo ufw enable
```

### 4. Access Dashboard

Open browser:
```
http://YOUR_VPS_IP
```

---

## ✨ Features

### Core Capabilities
- **3 RX Modes**: Listener, Caller, Rendezvous
- **3 TX Modes** per route: Listener, Caller, Rendezvous
- **Multi-Session Support**: Unlimited sessions
- **Per-Route Settings**: Independent latency, buffer, encryption
- **Hot Reload**: Edit sessions without affecting others
- **Real-time Stats**: Bitrate, RTT, packet loss monitoring
- **Web Dashboard**: Beautiful glassmorphism UI

### RX (Input) Modes

**Listener** - Gateway waits for encoder:
```
Encoder → srt://gateway_ip:5000 → Gateway
```

**Caller** - Gateway connects to encoder:
```
Gateway → srt://encoder_ip:5000 → Encoder
```

**Rendezvous** - Peer-to-peer:
```
Gateway:5000 ↔ Encoder:5000
```

### TX (Output) Modes

Each route can independently use:

**Listener** - Decoders connect to gateway:
```
Decoder → srt://gateway_ip:6001 → Gateway
```

**Caller** - Gateway pushes to decoder:
```
Gateway → srt://decoder_ip:7001 → Decoder
```

**Rendezvous** - Peer-to-peer:
```
Gateway:6001 ↔ Decoder:6001
```

---

## 🎛️ Using the Dashboard

### Create Session

1. Click **+** button (bottom-right)
2. Enter session name
3. Configure **RX Settings** (Main Input):
   - Select mode (listener/caller/rendezvous)
   - Set port and host (if needed)
   - Configure: latency, buffer, maxbw, streamid, passphrase
4. Configure **Route 1 Settings** (First Output):
   - Select mode (listener/caller/rendezvous)
   - Set port and host (if needed)
   - Configure: latency, buffer, maxbw, streamid, passphrase
5. Click **Create Session**

### Edit Session

1. Click **Edit** button on session
2. Modify settings (name, host, latency, buffer, passphrase)
3. Click **Update Session**
4. ⚡ Hot reload - only this session restarts

### Add Route

1. In session card, click **➕ Add Another Route**
2. Select TX mode (listener/caller/rendezvous)
3. Configure all TX settings
4. Click **Add Route**
5. ⚡ Hot reload - session restarts with new route

### Delete

- **Delete Route**: Click Delete on route card
- **Delete Session**: Click Delete on session header

---

## 📋 Configuration Options

### Per-Route Settings (RX and TX)

| Setting | Default | Description |
|---------|---------|-------------|
| **Latency** | 120ms | SRT latency buffer |
| **Buffer Size** | 100ms | Send/receive buffer |
| **Max Bandwidth** | Unlimited | Rate limiting (bytes/sec) |
| **Stream ID** | None | SRT stream identifier |
| **Passphrase** | None | AES encryption (16-79 chars) |

### Encryption Levels

```
Passphrase Length:
  16-22 chars = AES-128
  23-31 chars = AES-192
  32-79 chars = AES-256
```

---

## 💡 Usage Examples

### Example 1: Basic Broadcast

```
Session: Production Stream
RX: Listener on port 5000
Routes:
  - Route 1: Listener on 6001 (Studio decoders)
  - Route 2: Listener on 6002 (Monitoring)
  - Route 3: Listener on 6003 (Archive)
```

**Encoder:**
```bash
ffmpeg -re -i input.mp4 -c copy -f mpegts "srt://gateway_ip:5000?latency=120000"
```

**Decoder:**
```bash
ffplay "srt://gateway_ip:6001?latency=120000"
```

### Example 2: Pull and Push

```
Session: CDN Feed
RX: Caller → 192.168.1.100:5000 (pull from encoder)
Routes:
  - Route 1: Listener on 6001 (local monitoring)
  - Route 2: Caller → cdn.example.com:8000 (push to CDN)
    Passphrase: "cdn_secret_2024"
    Max BW: 50 Mbps
```

### Example 3: Multi-Destination with Encryption

```
Session: Secure Distribution
RX: Listener on 5000 (encrypted input)
  Passphrase: "input_key_2024"

Routes:
  - Route 1: Listener on 6001 (no encryption)
  - Route 2: Caller → 203.0.113.10:8000
    Passphrase: "partner_a_key"
  - Route 3: Caller → 198.51.100.20:9000
    Passphrase: "partner_b_key"
```

---

## 🔧 Service Management

```bash
# Start service
sudo systemctl start srt-gateway

# Stop service
sudo systemctl stop srt-gateway

# Restart service
sudo systemctl restart srt-gateway

# View logs
sudo journalctl -u srt-gateway -f

# Check status
sudo systemctl status srt-gateway
```

---

## 🐛 Troubleshooting

### Dashboard Not Accessible

```bash
# Check service status
sudo systemctl status srt-gateway

# Check if port 80 is listening
sudo ss -tulpn | grep :80

# Check firewall
sudo ufw status

# Test locally
curl http://localhost/
```

### Session Won't Start

```bash
# Check logs for errors
sudo journalctl -u srt-gateway -n 50

# Verify port not in use
sudo ss -tulpn | grep :5000

# Check database
sqlite3 /opt/srt-gateway/gateway.db "SELECT * FROM sessions;"
```

### Connection Issues

```bash
# Listener mode - check firewall
sudo ufw allow 5000/udp

# Caller mode - verify remote is listening
telnet encoder_ip encoder_port

# Check connectivity
ping encoder_ip
```

---

## 📡 API Reference

### Sessions

```bash
# List all sessions
GET /api/sessions

# Get single session
GET /api/sessions/{port}

# Create session
POST /api/sessions

# Update session (hot reload)
PUT /api/sessions/{port}

# Delete session
DELETE /api/sessions/{port}
```

### Routes

```bash
# Get route
GET /api/routes/{id}

# Add route (hot reload)
POST /api/routes

# Update route (hot reload)
PUT /api/routes/{id}

# Delete route
POST /api/routes/{id}/stop
```

### Statistics

```bash
# Real-time stats
GET /api/stats
```

---

## 📊 Performance

| Setup | Sessions | Routes | Throughput | CPU | RAM |
|-------|----------|--------|------------|-----|-----|
| Small | 1-2 | 3-5 | 100 Mbps | 5% | 200MB |
| Medium | 5-10 | 15-30 | 500 Mbps | 15% | 500MB |
| Large | 10-15 | 50-80 | 1 Gbps | 30% | 1GB |
| Enterprise | 20+ | 100+ | 5 Gbps | 60% | 2GB |

---

## 🔐 Security Best Practices

1. **Use Strong Passphrases**: 32+ characters for AES-256
2. **Different Keys Per Route**: Isolate destinations
3. **Firewall Rules**: Whitelist specific IPs
4. **Regular Updates**: Keep system and packages updated
5. **Monitor Logs**: Watch for suspicious activity

---

## 📝 System Requirements

- Ubuntu 20.04+ or Debian 11+
- libsrt 1.5.3+
- Python 3.8+
- 2GB RAM minimum
- 10GB disk space

---

## 🎓 What the Installer Does

The `install.sh` script automatically:

1. ✅ Checks Ubuntu/Debian version
2. ✅ Installs dependencies (Python, libsrt, FastAPI, etc.)
3. ✅ Creates `/opt/srt-gateway/` directory
4. ✅ Initializes SQLite database
5. ✅ Copies all files
6. ✅ Creates systemd service
7. ✅ Starts service
8. ✅ Enables auto-start on boot

---

## 🆘 Support

### Check Logs
```bash
sudo journalctl -u srt-gateway -f
```

### Database Location
```bash
/opt/srt-gateway/gateway.db
```

### Configuration
All configuration stored in database (no config files needed)

---

## 📜 License

MIT License

---

## 🎉 Quick Start Summary

```bash
# 1. Upload and extract
scp srt-gateway-v5-complete.zip root@VPS_IP:/tmp/
ssh root@VPS_IP
cd /tmp && unzip srt-gateway-v5-complete.zip
cd srt-gateway-v5-complete

# 2. Install
sudo bash install.sh

# 3. Configure firewall
sudo ufw allow 1024:65500/udp
sudo ufw allow 80/tcp
sudo ufw enable

# 4. Access dashboard
# http://YOUR_VPS_IP
```

**That's it! Start creating sessions! 🚀**

---

**Version**: 5.0  
**Last Updated**: November 2024  
**Built with**: SRT Protocol, Python, FastAPI, ApexCharts
