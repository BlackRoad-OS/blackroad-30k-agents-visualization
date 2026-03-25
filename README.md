<!-- BlackRoad SEO Enhanced -->

# ulackroad 30k agents visualization

> Part of **[BlackRoad OS](https://blackroad.io)** — Sovereign Computing for Everyone

[![BlackRoad OS](https://img.shields.io/badge/BlackRoad-OS-ff1d6c?style=for-the-badge)](https://blackroad.io)
[![BlackRoad-Agents](https://img.shields.io/badge/Org-BlackRoad-Agents-2979ff?style=for-the-badge)](https://github.com/BlackRoad-Agents)

**ulackroad 30k agents visualization** is part of the **BlackRoad OS** ecosystem — a sovereign, distributed operating system built on edge computing, local AI, and mesh networking by **BlackRoad OS, Inc.**

### BlackRoad Ecosystem
| Org | Focus |
|---|---|
| [BlackRoad OS](https://github.com/BlackRoad-OS) | Core platform |
| [BlackRoad OS, Inc.](https://github.com/BlackRoad-OS-Inc) | Corporate |
| [BlackRoad AI](https://github.com/BlackRoad-AI) | AI/ML |
| [BlackRoad Hardware](https://github.com/BlackRoad-Hardware) | Edge hardware |
| [BlackRoad Security](https://github.com/BlackRoad-Security) | Cybersecurity |
| [BlackRoad Quantum](https://github.com/BlackRoad-Quantum) | Quantum computing |
| [BlackRoad Agents](https://github.com/BlackRoad-Agents) | AI agents |
| [BlackRoad Network](https://github.com/BlackRoad-Network) | Mesh networking |

**Website**: [blackroad.io](https://blackroad.io) | **Chat**: [chat.blackroad.io](https://chat.blackroad.io) | **Search**: [search.blackroad.io](https://search.blackroad.io)

---


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
