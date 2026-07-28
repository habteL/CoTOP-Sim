import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import random
import numpy as np
from cotopsim.environment import CoToPEnvironment

SEED         = 42
NUM_EPISODES = 10
TASKS_PER_EP = 25

def run_policy(policy_fn, policy_name, num_episodes=NUM_EPISODES):
    """Run a fixed policy for num_episodes and return avg metrics."""
    results = []

    for episode in range(num_episodes):
        env = CoToPEnvironment(
            num_vehicles=1, max_steps=TASKS_PER_EP+10,
            sigma=0.3, seed=SEED + episode
        )
        state = env.reset()
        tasks = env.generate_episode_tasks(target_tasks=TASKS_PER_EP)

        total_reward = 0.0
        for task in tasks:
            serving_rsu = env._find_serving_rsu(env.vehicles[0])
            action = policy_fn(state, serving_rsu, env)
            state, reward, done, info = env.step(
                action=action, current_task=task)
            total_reward += reward
            if done:
                break

        metrics = env.get_metrics()
        metrics['total_reward'] = total_reward
        results.append(metrics)
    metrics = env.get_metrics()
    # print(f"completed={metrics['completed']} "
    #     f"failed={metrics['failed']} "
    #     f"pending={metrics['pending']} "
    #     f"generated={metrics['generated']}")
    metrics['total_reward'] = total_reward
    results.append(metrics)
    avg = {
        'policy'           : policy_name,
        'avg_reward'       : np.mean([r['total_reward']     for r in results]),
        'avg_delay'        : np.mean([r['avg_delay']        for r in results]),
        'avg_energy'       : np.mean([r['avg_energy']       for r in results]),
        'completion_ratio' : np.mean([r['completion_ratio'] for r in results]),
    }
    return avg

# ── Policy 1: Always standalone ───────────────────────────────
def always_standalone(state, serving_rsu, env):
    return 0

# ── Policy 2: Always collaborate with nearest neighbor ────────
def always_collaborate(state, serving_rsu, env):
    if serving_rsu and serving_rsu.neighbor_ids:
        return serving_rsu.neighbor_ids[-1]  # next RSU
    return 0

# ── Policy 3: Greedy — collaborate only if dwell time short ───
def greedy(state, serving_rsu, env):
    if serving_rsu is None:
        return 0
    v      = env.vehicles[0]
    t_stay = v.estimate_dwell_time(serving_rsu)
    # Collaborate if dwell time < 2s (task may not finish)
    if t_stay < 2.0 and serving_rsu.neighbor_ids:
        return serving_rsu.neighbor_ids[-1]
    return 0

# ── Run all three ─────────────────────────────────────────────
if __name__ == "__main__":
    random.seed(SEED)
    np.random.seed(SEED)

    print("=== CoTOP Heuristic Baseline Evaluation ===")
    print(f"Episodes: {NUM_EPISODES} | Tasks/ep: {TASKS_PER_EP}\n")

    policies = [
        (always_standalone,  "Always Standalone"),
        (always_collaborate, "Always Collaborate"),
        (greedy,             "Greedy (dwell-based)"),
    ]

    print(f"{'Policy':<22} | {'Reward':>8} | "
          f"{'Delay':>7} | {'Energy':>8} | {'Completion':>10}")
    print("-" * 65)

    for fn, name in policies:
        result = run_policy(fn, name)
        print(f"{name:<22} | {result['avg_reward']:>8.2f} | "
              f"{result['avg_delay']:>7.3f}s | "
              f"{result['avg_energy']:>8.3f}J | "
              f"{result['completion_ratio']:>10.3f}")