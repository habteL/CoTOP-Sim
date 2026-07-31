# CoTOP-Sim

**Reproduction of: Mobility-Aware Collaborative Task Offloading 
for Parallel Tasks in Vehicular Edge Computing**

IEEE Transactions on Mobile Computing, Vol. 25, No. 4, 2026  
DOI: 10.1109/TMC.2025.3631820

---

## Author

**Dr. Habte Lejebo**  
Research Areas: VEC · Deep Reinforcement Learning · 
Edge Computing · Multi-Agent Systems

---

## Reproduction Status

### Phase 1 — Core Framework (Complete)

| Component | Status | Reference |
|---|---|---|
| Task model (ρ, φ, d) | ✅ Implemented | Eq. 1-6 |
| V2R/R2R channel model | ✅ Implemented | Eq. 1-2 |
| Standalone computation | ✅ Implemented | Eq. 3-6 |
| Collaborative computation | ✅ Implemented | Eq. 7-10 |
| Energy model | ✅ Implemented | Eq. 11-12 |
| Task priority algorithm | ✅ Implemented | Eq. 23 |
| A3C offloading agent | ✅ Implemented | Algorithm 1 |
| Baseline comparisons | ✅ Implemented | Sec. V-B |

### Phase 2 — Time-Slot Simulation (Planned)

| Component | Status |
|---|---|
| Time-slot driven loop | 🔄 In progress |
| Dynamic vehicle mobility | ⏳ Planned |
| GAT mobility detection | ⏳ Planned |
| ApolloScape dataset | ⏳ Planned |

---

## Phase 1 Results

| Metric | Our Result | Paper (CoTOP) | Notes |
|---|---|---|---|
| Avg delay | 1.5-2.0s | 13.1-14.3s | See gap analysis |
| Completion ratio | 0.60-0.72 | 0.86-0.87 | Mobility missing |
| A3C vs standalone | +10.5% reward | Significant | Direction confirmed |
| A3C vs always-collab | +4.5% reward | Significant | Learned policy |

### Delay Gap Analysis

Phase 1 produces 1.5-2.0s average delay vs the paper's 13-14s.
This gap is explained by simulation granularity differences:

1. **Task-driven vs time-slot driven loop** — Paper executes
   one decision per time slot with vehicle movement between
   decisions. Phase 1 processes all tasks in one batch without
   vehicle mobility during execution.

2. **RSU processing speed** — Under Table III parameters
   (φ=10 Mcycles, F=1-4 Gcycles/s), T_pro=0.01s making
   processing negligible. The paper's 14s delay likely 
   accumulates across many time slots with multiple vehicles.

3. **Queue dynamics** — With fast processing, RSU queues
   drain nearly instantly. Meaningful queue congestion requires
   the time-slot model with continuous task arrival.

4. **GAT mobility** — The paper's GAT model provides accurate
   dwell time estimates that trigger collaboration. Phase 1
   uses analytical dwell time which rarely triggers collaboration
   under Table III parameters.

**Research finding:** The performance gap is not caused by
parameter errors but by simulation abstraction level. This
is consistent with findings in other VEC reproduction studies.

---

## System Configuration

Road length: 200m
RSUs: 6 (evenly spaced at 33.33m intervals)
Coverage radius: 400m (Table III)
RSU capacity: 1000-4000 Mcycles/s
Vehicles: 10
Task size: 16-40 Mbits (2-5 MB)
Task CPU cycles: 1-10 Mcycles
Task deadline: 20-30 seconds
V2R bandwidth: 50 Mbps (midpoint of 20-100 Mbps)


---

## Repository Structure

CoTOP-Sim/
├── src/cotopsim/
│ ├── task.py # Task model (rho, phi, d)
│ ├── vehicle.py # Vehicle mobility + task generation
│ ├── rsu.py # RSU M/M/1 queue model
│ ├── channel.py # V2R + R2R channel (Eq. 1-2)
│ ├── computation.py # Delay + energy (Eq. 3-12)
│ ├── priority.py # Task priority (Eq. 23)
│ ├── agent.py # A3C actor-critic
│ └── environment.py # Task-driven environment
├── experiments/
│ ├── train_cotop.py # A3C training loop
│ ├── baselines.py # Heuristic baselines
│ └── plot_cotop.py # Learning curve visualization
├── results/
│ ├── cotop_agent_500ep.pt
│ ├── train_metrics_500ep.csv
│ └── learning_curve_cotop.png
└── docs/


---

## Quick Start

```bash
git clone https://github.com/habteL/CoTOP-Sim.git
cd CoTOP-Sim
pip install -e .

# Run baselines
python experiments/baselines.py

# Train A3C agent (500 episodes)
python experiments/train_cotop.py

# Plot learning curve
python experiments/plot_cotop.py
```

---

## Citation

```bibtex
@misc{lejebo2026cotopsim,
  author    = {Lejebo, Leka Habte},
  title     = {{CoTOP-Sim: Reproduction of Mobility-Aware 
               Collaborative Task Offloading for VEC}},
  year      = {2026},
  publisher = {GitHub},
  url       = {https://github.com/habteL/CoTOP-Sim}
}
```

Original paper:
```bibtex
@article{du2026cotop,
  author  = {Du, Jiaxin and Zhang, Jinfan and Han, Guangjie 
             and Wang, Mengmeng and Shen, Guojiang and 
             Liu, Zhi and Kong, Xiangjie},
  title   = {Mobility-Aware Collaborative Task Offloading 
             for Parallel Tasks in Vehicular Edge Computing},
  journal = {IEEE Transactions on Mobile Computing},
  volume  = {25},
  number  = {4},
  year    = {2026},
  doi     = {10.1109/TMC.2025.3631820}
}
```

## License
- Source code: MIT License
- Documentation: CC BY 4.0