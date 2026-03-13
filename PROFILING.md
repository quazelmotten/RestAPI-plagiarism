# Profiling Guide

This project uses **Py-Spy** for low-overhead profiling of Python applications. Py-Spy is a sampling profiler that can inspect running Python processes without requiring code changes or restarting services.

## 📦 Installation

Py-Spy is already included in the requirements files. If you need to install it manually:

```bash
# On the host system (for running scripts directly on processes)
pip install py-spy

# Or if using the containerized approach, it's already installed in the Docker images
```

## 🚀 Quick Start

### Using the Provided Scripts

Three profiling scripts are available in the `scripts/` directory:

#### 1. Profile API (Flame Graph)
```bash
./scripts/profile-api.sh 30
```
Profiles the API for 30 seconds and generates `profiles/api-profile-<timestamp>.svg`.

#### 2. Profile Worker (Flame Graph)
```bash
./scripts/profile-worker.sh 30
```
Profiles the worker for 30 seconds and generates `profiles/worker-profile-<timestamp>.svg`.

#### 3. Real-time Top-like Profiling
```bash
./scripts/profile-top.sh api      # Monitor API in real-time
./scripts/profile-top.sh worker  # Monitor worker in real-time
```
Shows a live view of what functions are consuming CPU. Press Ctrl+C to stop.

### Using Quick Command Script

All profiling commands are also available via the quick command script:

```bash
./scripts/quick-cmd.sh prof-api 60       # Profile API for 60 seconds
./scripts/quick-cmd.sh prof-worker 60    # Profile worker for 60 seconds
./scripts/quick-cmd.sh prof-top api      # Real-time API profiling
./scripts/quick-cmd.sh prof-top worker  # Real-time worker profiling
```

## 📊 Understanding the Output

### Flame Graphs (SVG)

The SVG flame graphs show:
- **Y-axis**: Call stack depth (top = root, bottom = leaves)
- **X-axis**: Sample count (wider = more CPU time)
- **Colors**: Warm colors = more samples, cool colors = fewer samples

**Interpreting the graph:**
- Wide bars at the top indicate hotspots in your code
- Follow the stack down to see which functions are being called
- Hover over frames to see exact function names and sample percentages

### Real-time Top View

Shows:
- Current function being executed
- % of samples for that function
- Call stack
- Line numbers (if symbols are available)

## 🔍 Profiling Scenarios

### 1. Finding API Endpoint Slowness

Profile the API while making requests:

```bash
# Terminal 1: Start profiling
./scripts/profile-api.sh 60

# Terminal 2: Generate load (in another terminal)
ab -n 100 -c 10 http://localhost:8000/api/plagiarism/check
# or use the frontend to exercise specific endpoints
```

After 60 seconds, open the SVG and look for:
- FastAPI routing functions (`router_plagiarism`, `router_auth`)
- Database query methods
- External API calls (if any)
- File processing code

### 2. Analyzing Worker Performance

Profile the worker during file processing:

```bash
# Upload a file through the API to trigger worker processing
# Then immediately profile the worker:
./scripts/profile-worker.sh 60
```

Look for:
- `process_file` or similar processing functions
- Tree-sitter parsing calls
- Redis/inverted index operations
- Database writes
- `xxhash` computation

### 3. Real-time Monitoring

Use the top view to see what's happening right now:

```bash
./scripts/profile-top.sh worker
```

This is useful for:
- Verifying the system is working (not stuck)
- Seeing which stage of processing is active
- Quick checks during development

## 🐳 Docker Container Profiling Notes

The profiling scripts work by:
1. Finding the process ID inside the container (`pgrep -f "uvicorn"` or `pgrep -f "worker.py"`)
2. Executing `py-spy` inside the container attached to that PID
3. Copying the generated SVG output to the host

**Important:**
- The containers must be running (`docker-compose up -d`)
- Py-spy must be installed in the container (already in requirements.txt)
- The scripts assume the default Docker Compose service names: `api`, `worker`

### Docker Security Capabilities

Py-spy requires the `SYS_PTRACE` capability to attach to processes. By default, this project uses `no-new-privileges:true` for security, which blocks profiling.

To enable profiling, use the provided `docker-compose.profiling.yml` override:

```bash
# Stop current services
docker-compose down

# Start with profiling capabilities
docker-compose -f docker-compose.yml -f docker-compose.profiling.yml up -d --build
```

The override file:
- Disables `no-new-privileges` restriction
- Adds `SYS_PTRACE` capability
- Increases PID limit for better sampling

After profiling, return to normal operation:
```bash
docker-compose -f docker-compose.yml -f docker-compose.profiling.yml down
docker-compose up -d
```

The profiling scripts will automatically detect the override and use it if available. If you get "Operation not permitted", restart with the override as shown above.

## 🛠️ Advanced Usage

### Profile for Different Durations

```bash
./scripts/profile-api.sh 120    # 2 minutes
./scripts/profile-api.sh 10     # 10 seconds (quick check)
```

### Capture a Text Dump Instead of Flame Graph

```bash
# Get PID first (or modify script)
PID=$(docker-compose exec -T api pgrep -f "uvicorn")
docker-compose exec -T api py-spy dump -p $PID > api-profile.txt
```

The text dump shows the same information as the flame graph but in text form with line numbers.

### Profile Specific Function Only

Use `py-spy record --include-children` to see all functions in the call stack, or use `py-spy top -n` to toggle between native and Python frames.

## 🔧 Troubleshooting

### "Could not find process" error

Make sure the service is running:
```bash
docker-compose ps
```

Check the process name inside the container:
```bash
docker-compose exec api ps aux
```

### Permission denied

If py-spy cannot attach to the process, ensure the container is running as root (default). Some Docker setups may restrict process inspection. In that case, you may need to run with elevated privileges.

### No Python symbols

If the output shows many frames as `<unknown>` or `???:0`, it means the container doesn't have Python debug symbols. This is normal for production containers. For best results, use a development build with debug symbols or rebuild with `--build-arg PYTHON_DEBUG=1`.

### SVG not opening

The SVG should open in any modern browser. If it doesn't render, try:
- Opening in a different browser
- Checking file permissions
- Converting to another format: `py-spy merge -o profile.json profile.svg`

## 📈 Interpreting Results for Optimization

1. **Identify Hotspots**: Look for the widest bars at the top of the flame graph.
2. **Check I/O Bound Functions**: If many samples are in `time.sleep`, database drivers, or network I/O, the bottleneck may be external.
3. **Lock Contention**: If multiple threads show the same function, there may be GIL or lock contention.
4. **Algorithm Complexity**: Deep call stacks with many samples in loops may indicate O(n²) or worse algorithms.
5. **Memory Allocation**: Look for time spent in `__alloc__` or `__new__` if memory pressure is high.

## 🔄 Continuous Profiling

For ongoing performance monitoring, consider integrating Py-Spy with:

- **Pyroscope** (continuous profiling platform)
- **Datadog** or **New Relic** (APM solutions)
- Custom cron jobs that periodically profile and archive results

Example cron job (run hourly):
```bash
0 * * * * cd /path/to/project && ./scripts/profile-api.sh 60
```

## 📚 Additional Resources

- [Py-Spy Documentation](https://github.com/benfred/py-spy)
- [Flame Graph Documentation](https://www.brendangregg.com/flamegraphs.html)
- [Python Profiling Best Practices](https://docs.python.org/3/library/profile.html)
