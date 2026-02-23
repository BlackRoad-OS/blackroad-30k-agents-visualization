# blackroad-30k-agents-visualization

Visualization data engine for the BlackRoad 30K agent fleet. Generates node stats, distribution chart data, capacity metrics, and live agent states for dashboard rendering.

## Install

```bash
pip install -e .
```

## Usage

```bash
# Node statistics
python src/visualization.py stats

# Distribution by type or status
python src/visualization.py distribution --dimension type
python src/visualization.py distribution --dimension status

# Capacity metrics
python src/visualization.py capacity

# Live agent states
python src/visualization.py live --limit 20 --status online

# Generate chart JSON
python src/visualization.py chart type_distribution
python src/visualization.py chart node_capacity

# Export full dashboard snapshot
python src/visualization.py export --output snapshot.json
```

## Architecture

- SQLite multi-table persistence (`~/.blackroad/visualization.db`)
- Dataclasses: `NodeStats`, `DistributionBucket`, `CapacityMetric`, `LiveAgentState`, `ChartData`
- Simulates 30,000 agents across 5 nodes
- Chart-ready JSON output for any frontend renderer

## Development

```bash
pip install pytest pytest-cov flake8
pytest tests/ -v --cov=src
```
