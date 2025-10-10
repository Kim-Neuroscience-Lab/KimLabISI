# ISI Macroscope Backend - Deployment Checklist

## Pre-Deployment Verification

### System Requirements

- [ ] Python 3.10+ installed
- [ ] Virtual environment created (`.venv/`)
- [ ] All dependencies installed (`poetry install` or `pip install -r requirements.txt`)
- [ ] Sufficient disk space (minimum 10GB for data storage)
- [ ] Sufficient RAM (minimum 8GB, recommended 16GB+)
- [ ] GPU drivers updated (if using GPU acceleration)

**Verify:**
```bash
cd /Users/Adam/KimLabISI/apps/backend
.venv/bin/python --version  # Should be 3.10+
.venv/bin/python -c "import numpy, scipy, h5py, cv2, zmq; print('OK')"
df -h .  # Check disk space
```

### Configuration

- [ ] Configuration file exists: `config/isi_parameters.json`
- [ ] Configuration validates successfully
- [ ] Backup of current configuration created
- [ ] Camera configuration correct (if using hardware)
- [ ] Display configuration correct (if using stimulus display)
- [ ] IPC ports available (5555, 5557, 5558, 5559)

**Verify:**
```bash
# Validate configuration
.venv/bin/python src/migrate_config.py --validate

# Create backup
.venv/bin/python src/migrate_config.py --backup --label "pre_deployment"

# Check ports are free
lsof -i :5555 -i :5557 -i :5558 -i :5559
# Should return nothing (ports available)
```

### Testing

- [ ] All phase tests pass (Phase 1-7)
- [ ] Integration tests pass
- [ ] Code quality checks pass
- [ ] Master test suite passes
- [ ] Zero service_locator imports in new code
- [ ] All modules import successfully
- [ ] No circular dependencies detected

**Verify:**
```bash
# Run comprehensive test suite
.venv/bin/python src/test_all.py

# Expected output: "OVERALL RESULT: ALL TESTS PASSED"
```

### Code Quality

- [ ] No service_locator anti-pattern in new code
- [ ] No global singletons (provide_* functions)
- [ ] All classes use constructor injection
- [ ] Module structure follows conventions
- [ ] Docstrings present in all modules
- [ ] Naming conventions followed

**Verify:**
```bash
# Run quality checks
.venv/bin/python src/test_quality.py

# Expected output: "CODE QUALITY TESTS: PASSED"
```

## Deployment Steps

### Step 1: Stop Old System

- [ ] Identify running backend processes
- [ ] Stop old backend gracefully
- [ ] Verify ports are released
- [ ] Archive logs from old system

**Execute:**
```bash
# Find running processes
ps aux | grep "isi_control.main"
ps aux | grep "src.main"

# Stop gracefully (send SIGTERM)
pkill -TERM -f "isi_control.main"
pkill -TERM -f "src.main"

# Wait for shutdown (up to 10 seconds)
sleep 2

# Force kill if still running
pkill -KILL -f "isi_control.main"
pkill -KILL -f "src.main"

# Verify ports released
lsof -i :5555  # Should return nothing
```

### Step 2: Clean Environment

- [ ] Clear shared memory segments
- [ ] Remove stale lock files
- [ ] Clean temporary files
- [ ] Verify IPC sockets closed

**Execute:**
```bash
# Check for shared memory segments
ipcs -m | grep stimulus_stream

# Remove if exists (replace SHMID with actual ID)
# ipcrm -m <SHMID>

# Clean temp files (if any)
# rm -f /tmp/isi_macroscope_*
```

### Step 3: Start New System

- [ ] Launch new backend
- [ ] Verify startup logs show no errors
- [ ] Confirm IPC channels initialized
- [ ] Check shared memory created
- [ ] Verify service creation completes

**Execute:**
```bash
# Start new backend (foreground for initial test)
cd /Users/Adam/KimLabISI/apps/backend
.venv/bin/python src/main.py

# Expected log output:
# [INFO] ISI Macroscope Control System - Refactored Backend
# [INFO] Creating services (composition root)...
# [INFO]   [1/11] MultiChannelIPC created
# ...
# [INFO]   [11/11] AcquisitionManager created
# [INFO] Created XX command handlers
# [INFO] Backend ready - entering event loop
```

### Step 4: Verify System Health

- [ ] Backend process running
- [ ] IPC ports listening
- [ ] Shared memory segment created
- [ ] No error messages in logs
- [ ] Health check responds

**Execute:**
```bash
# Verify process running
ps aux | grep "src.main"

# Verify ports listening
lsof -i :5555 -i :5558  # Should show python processes

# Send health check (requires IPC client or frontend)
# echo '{"type":"health_check"}' | nc localhost 5555
```

### Step 5: Hardware Detection

- [ ] Camera detection works (if using camera)
- [ ] Display detection works (if using display)
- [ ] Shared memory accessible
- [ ] Frame capture works (if using camera)

**Execute:**
```bash
# Test camera detection (via IPC)
# Send: {"type": "detect_cameras"}
# Expected: {"success": true, "cameras": [...]}

# Test display detection
# Send: {"type": "get_system_status"}
# Expected: {"success": true, "backend_running": true}
```

### Step 6: Frontend Integration

- [ ] Frontend can connect to backend
- [ ] IPC communication works
- [ ] Shared memory frames display
- [ ] Commands execute successfully
- [ ] Parameters can be updated

**Execute:**
```bash
# Start frontend (if separate process)
# Verify connection in frontend logs

# Test basic commands from frontend:
# - ping
# - get_system_status
# - get_all_parameters
# - detect_cameras
```

## Post-Deployment Validation

### Functional Tests

- [ ] Camera acquisition starts/stops
- [ ] Stimulus generation works
- [ ] Frame capture works
- [ ] Data recording works
- [ ] Analysis pipeline works
- [ ] Playback mode works
- [ ] Parameter updates work

### Performance Tests

- [ ] CPU usage acceptable (<50% idle, <90% under load)
- [ ] Memory usage stable (no leaks)
- [ ] Frame rate achieves target (30 FPS typical)
- [ ] IPC latency acceptable (<10ms)
- [ ] Shared memory throughput adequate

**Monitor:**
```bash
# Monitor CPU/memory
top -pid $(pgrep -f "src.main")

# Watch for memory leaks (run for 5+ minutes)
# Memory should stabilize after initialization
```

### Reliability Tests

- [ ] System runs for 10+ minutes without errors
- [ ] No crashes or exceptions
- [ ] Graceful shutdown works (Ctrl+C)
- [ ] System can restart cleanly
- [ ] Error recovery works (e.g., camera disconnect)

## Production Deployment

### Daemonize (Optional)

For production deployment, run as background service:

**Using systemd (Linux):**

Create `/etc/systemd/system/isi-macroscope.service`:
```ini
[Unit]
Description=ISI Macroscope Backend
After=network.target

[Service]
Type=simple
User=<your-user>
WorkingDirectory=/Users/Adam/KimLabISI/apps/backend
ExecStart=/Users/Adam/KimLabISI/apps/backend/.venv/bin/python src/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable isi-macroscope
sudo systemctl start isi-macroscope
sudo systemctl status isi-macroscope
```

**Using screen (Simple):**
```bash
# Start in detached screen session
screen -dmS isi-macroscope bash -c 'cd /Users/Adam/KimLabISI/apps/backend && .venv/bin/python src/main.py'

# Reattach to view
screen -r isi-macroscope

# Detach: Ctrl+A, D
```

### Logging

- [ ] Log file created: `logs/isi_macroscope.log`
- [ ] Log rotation configured (if long-running)
- [ ] Log level appropriate (INFO for production)
- [ ] Error alerts configured (optional)

**Configure log rotation:**
Create `/etc/logrotate.d/isi-macroscope`:
```
/Users/Adam/KimLabISI/apps/backend/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### Monitoring

- [ ] Process monitoring enabled (systemd/supervisord)
- [ ] Health check endpoint responsive
- [ ] Resource monitoring (CPU/RAM/disk)
- [ ] Alert on failures (optional)

## Rollback Plan

If deployment fails:

### Emergency Rollback

1. **Stop new backend:**
   ```bash
   pkill -TERM -f "src.main"
   ```

2. **Restore old configuration (if changed):**
   ```bash
   .venv/bin/python src/migrate_config.py --restore
   ```

3. **Start old backend:**
   ```bash
   .venv/bin/python -m isi_control.main
   # Or: isi-macroscope-old
   ```

4. **Verify old system works:**
   - Frontend connects
   - Camera acquisition works
   - Data recording works

### Post-Rollback

- [ ] Document failure reason
- [ ] Create bug report
- [ ] Analyze logs
- [ ] Fix issues in development
- [ ] Re-test before next deployment attempt

## Success Criteria

Deployment is successful when:

- ✅ All tests pass
- ✅ Backend starts without errors
- ✅ Frontend connects successfully
- ✅ Hardware detection works
- ✅ Frame acquisition works
- ✅ System runs stable for 30+ minutes
- ✅ No memory leaks detected
- ✅ Performance meets requirements
- ✅ Error handling works correctly

## Deployment Sign-Off

**Deployment Date:** ________________

**Deployed By:** ________________

**Verification:**

- [ ] Pre-deployment checklist complete
- [ ] All tests passed
- [ ] System deployed successfully
- [ ] Post-deployment validation complete
- [ ] Documentation updated
- [ ] Team notified

**Status:** ☐ SUCCESS  ☐ ROLLBACK  ☐ PARTIAL

**Notes:**
```
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
```

## Maintenance Schedule

### Daily
- [ ] Check log files for errors
- [ ] Verify system running
- [ ] Monitor disk space

### Weekly
- [ ] Review performance metrics
- [ ] Check for memory leaks
- [ ] Update dependencies (if needed)

### Monthly
- [ ] Run full test suite
- [ ] Review and archive old logs
- [ ] Backup configuration
- [ ] Security updates

## Contact Information

**System Owner:** ________________

**Technical Lead:** ________________

**Emergency Contact:** ________________

## Appendix: Troubleshooting

### Common Issues

**Issue: Port already in use**
```bash
# Find and kill process using port
lsof -i :5555
kill <PID>
```

**Issue: Shared memory error**
```bash
# List shared memory
ipcs -m
# Remove stale segment
ipcrm -m <SHMID>
```

**Issue: Import errors**
```bash
# Verify in correct directory
pwd  # Should be /Users/Adam/KimLabISI/apps/backend

# Verify virtual environment
which python  # Should point to .venv/bin/python
```

**Issue: Configuration not found**
```bash
# Check file exists
ls -la config/isi_parameters.json

# Validate configuration
.venv/bin/python src/migrate_config.py --validate
```

### Log Analysis

**Key log patterns to watch:**

✅ **Success:**
```
[INFO] Backend ready - entering event loop
[INFO] Processing command: <command_type>
[INFO] Command <command_type> completed
```

❌ **Errors:**
```
[ERROR] Handler error for <command>: <error>
[ERROR] Service creation failed: <error>
[ERROR] Fatal error: <error>
```

⚠️ **Warnings:**
```
[WARNING] Unknown command type: <type>
[WARNING] Camera not found: <camera>
```

---

**Document Version:** 1.0
**Last Updated:** Phase 8 Completion
**Next Review:** After 30 days production use
