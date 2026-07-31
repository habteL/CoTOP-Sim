import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import random
import numpy as np
import csv
import torch
from cotopsim.environment import CoToPEnvironment
from cotopsim.agent       import A3CAgent
from cotopsim.priority import PriorityAlgorithm 
# ── Reproducibility ───────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

# ── Hyperparameters ───────────────────────────────────────────
NUM_EPISODES   = 500
TASKS_PER_EP   = 25
UPDATE_FREQ    = 25      # update agent every N tasks
STATE_DIM      = 21
ACTION_DIM     = 7
LR             = 0.0002  # paper Table III best lr
GAMMA          = 0.99
SIGMA          = 0.3     # paper optimal α (delay/energy weight)

priority_model = PriorityAlgorithm(alpha=0.3, beta=0.7)
SAVE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'results', 'cotop_agent_500ep.pt')

METRICS_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'results', 'train_metrics_500ep.csv')

# ── Build environment and agent ───────────────────────────────
env   = CoToPEnvironment(
    num_vehicles = 10,
    max_steps    = TASKS_PER_EP * 2,
    sigma        = SIGMA,
    seed         = SEED
)
agent = A3CAgent(
    state_dim  = STATE_DIM,
    action_dim = ACTION_DIM,
    lr         = LR,
    gamma      = GAMMA
)

# ── Metrics storage ───────────────────────────────────────────
episode_logs = []

print("=== CoTOP Training ===")
print(f"Episodes:    {NUM_EPISODES}")
print(f"Tasks/ep:    {TASKS_PER_EP}")
print(f"Update freq: every {UPDATE_FREQ} tasks")
print(f"LR:          {LR}")
print(f"sigma:       {SIGMA}")
print()

# ── Training loop ─────────────────────────────────────────────
for episode in range(NUM_EPISODES):
    # Vary seed per episode for diverse task generation
    env.seed = SEED + episode
    state = env.reset()
    state1 = env._get_state()
    tasks = env.generate_episode_tasks(
        target_tasks=TASKS_PER_EP
    )

    # Algorithm 1 Line 10-11:
    # Compute task priority and sort tasks
    serving_rsu = env._find_serving_rsu(
        env.vehicles[0]
    )

    if serving_rsu:
        t_stay = env.vehicles[0].estimate_dwell_time(
            serving_rsu
        )
    else:
        t_stay = 1.0

    t_stay_map = {
        task.task_id: t_stay
        for task in tasks
    }

    tasks = priority_model.sort_tasks(
        tasks,
        t_stay_map
    )

    episode_reward    = 0.0
    actor_losses      = []
    critic_losses     = []
    standalone_count  = 0
    collab_count      = 0

    for task_idx, task in enumerate(tasks):

        # Build action mask — exclude current serving RSU
        serving_rsu = env._find_serving_rsu(env.vehicles[0])
        rsu_id      = serving_rsu.rsu_id if serving_rsu else None
        mask        = agent.build_mask(current_rsu_id=rsu_id)

        # Select action
        action, log_prob = agent.select_action(state, mask)

        # Track decision type
        if action == 0:
            standalone_count += 1
        else:
            collab_count += 1

        # Execute step
        next_state, reward, done, info = env.step(
            action=action, current_task=task)

        episode_reward += reward

        # Store experience
        agent.store(state, action, reward, mask)

        # Update every UPDATE_FREQ tasks or at episode end
        if (task_idx + 1) % UPDATE_FREQ == 0 or \
                task_idx == len(tasks) - 1:
            a_loss, c_loss = agent.update(next_state=next_state)
            if a_loss is not None:
                actor_losses.append(a_loss)
                critic_losses.append(c_loss)

        state = next_state

        if done:
            break
        # _, _, _, _ = env.step(action=0, current_task=tasks[0])
        # state2 = env._get_state()
        # print(f"Ep {episode}: states equal = {np.array_equal(state1, state2)}")
    scheduled = standalone_count + collab_count
    if scheduled < TASKS_PER_EP:
        print(f"  Warning ep {episode+1}: only {scheduled}/{TASKS_PER_EP} tasks scheduled")
    # ── Collect episode metrics ───────────────────────────────
    metrics = env.get_metrics()
    avg_actor  = np.mean(actor_losses)  if actor_losses  else 0.0
    avg_critic = np.mean(critic_losses) if critic_losses else 0.0

    log = {
        'episode'          : episode + 1,
        'total_reward'     : round(episode_reward, 4),
        'avg_delay'        : round(metrics['avg_delay'],        4),
        'avg_energy'       : round(metrics['avg_energy'],       4),
        'completion_ratio' : round(metrics['completion_ratio'], 4),
        'completed'        : metrics['completed'],
        'failed'           : metrics['failed'],
        'generated'        : metrics['generated'],
        'standalone'       : standalone_count,
        'collaborative'    : collab_count,
        'actor_loss'       : round(avg_actor,  4),
        'critic_loss'      : round(avg_critic, 4),
    }
    episode_logs.append(log)

    # ── Progress report every 10 episodes ─────────────────────
    if (episode + 1) % 10 == 0:
        print(f"Episode {episode+1:3d} | "
              f"reward={episode_reward:8.2f} | "
              f"completion={metrics['completion_ratio']:.3f} | "
              f"delay={metrics['avg_delay']:.3f}s | "
              f"solo={standalone_count} collab={collab_count}")

# ── Save agent and metrics ────────────────────────────────────
os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
agent.save(SAVE_PATH)

with open(METRICS_PATH, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=episode_logs[0].keys())
    writer.writeheader()
    writer.writerows(episode_logs)

print(f"\n=== Training Complete ===")
print(f"Agent saved:   {SAVE_PATH}")
print(f"Metrics saved: {METRICS_PATH}")

last = episode_logs[-1]
print(f"\nFinal episode metrics:")
print(f"  Total reward:     {last['total_reward']}")
print(f"  Completion ratio: {last['completion_ratio']}")
print(f"  Avg delay:        {last['avg_delay']}s")
print(f"  Avg energy:       {last['avg_energy']}J")
print(f"  Standalone:       {last['standalone']}")
print(f"  Collaborative:    {last['collaborative']}")