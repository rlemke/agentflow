# AgentFlow Examples

Each subdirectory contains a complete working example with AFL source and a Python agent implementation.

| Example | Description |
|---------|-------------|
| [hello-agent](hello-agent/) | Minimal end-to-end example demonstrating the AgentFlow execution model |
| [osm-geocoder](osm-geocoder/) | Geocoding agent that resolves addresses to coordinates using the OpenStreetMap Nominatim API |
| [genomics](genomics/) | Bioinformatics cohort analysis with foreach fan-out and linear fan-in workflows |
| [jenkins](jenkins/) | CI/CD pipelines showcasing mixin composition (Retry, Timeout, Credentials, etc.) |

## Running an Example

Each example has its own `README.md` with setup and run instructions. The general pattern is:

```bash
# From the repo root
source .venv/bin/activate

# Install example-specific dependencies
pip install -r examples/<name>/requirements.txt

# Compile the AFL source (syntax check)
scripts/compile examples/<name>/afl/*.afl --check

# Run the agent (see each example's README for details)
PYTHONPATH=. python examples/<name>/agent.py
```

## Writing a New Example

1. Create a directory under `examples/` with a descriptive name
2. Include at minimum:
   - `README.md` — what it does, prerequisites, how to run, expected output
   - `afl/*.afl` — AFL workflow source files
   - `agent.py` — Python agent using `AgentPoller`
   - `requirements.txt` — any extra pip dependencies
3. Add an entry to this README's table
