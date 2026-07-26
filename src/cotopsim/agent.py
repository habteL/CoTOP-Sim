import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

class ActorNetwork(nn.Module):
    """
    Actor network — outputs action probability distribution.
    3 FC layers as specified in CoTOP paper.
    """
    def __init__(self, state_dim, action_dim, hidden_dim=64):
        super().__init__()
        self.fc1 = nn.Linear(state_dim,  hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, action_dim)

    def forward(self, x, mask=None):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        logits = self.fc3(x)
        if mask is not None:
            logits = logits.masked_fill(mask == 0, float('-inf'))
        return F.softmax(logits, dim=-1)


class CriticNetwork(nn.Module):
    """
    Critic network — estimates state value V(s).
    3 FC layers as specified in CoTOP paper.
    """
    def __init__(self, state_dim, hidden_dim=64):
        super().__init__()
        self.fc1 = nn.Linear(state_dim,  hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)


class A3CAgent:
    """
    Synchronous A3C agent (A2C style) for CoTOP.
    Actor-Critic with action masking and entropy bonus.

    Loss: L = L_pi + c1*L_V - c2*H(pi)
    """

    def __init__(self,
                 state_dim  = 20,
                 action_dim = 7,
                 hidden_dim = 64,
                 lr         = 0.0002,   # paper Table III best lr
                 gamma      = 0.99,
                 c1         = 0.5,      # value loss weight
                 c2         = 0.01):    # entropy bonus weight
        self.state_dim  = state_dim
        self.action_dim = action_dim
        self.gamma      = gamma
        self.c1         = c1
        self.c2         = c2

        # ── Networks ──────────────────────────────────────────
        self.actor  = ActorNetwork(state_dim, action_dim, hidden_dim)
        self.critic = CriticNetwork(state_dim, hidden_dim)

        # ── Optimizers ────────────────────────────────────────
        self.actor_optimizer  = torch.optim.Adam(
            self.actor.parameters(),  lr=lr)
        self.critic_optimizer = torch.optim.Adam(
            self.critic.parameters(), lr=lr)

        # ── Experience buffer ─────────────────────────────────
        self.states      = []
        self.actions     = []
        self.rewards     = []
        self.masks       = []
        self.log_probs   = []

    def build_mask(self, current_rsu_id, num_rsus=6):
        """
        Build action mask (Option A).
        Action 0 = standalone always valid.
        Actions 1-6 = collaborate with RSU i.
        Mask out current RSU (redundant collaboration).
        """
        mask = torch.ones(self.action_dim)
        # Mask out collaborating with own RSU
        if current_rsu_id is not None:
            mask[current_rsu_id] = 0
        return mask

    def select_action(self, state, mask=None):
        """
        Sample action from actor distribution.
        Returns (action, log_prob).
        """
        state_t = torch.FloatTensor(state).unsqueeze(0)
        if mask is not None:
            mask_t = mask.unsqueeze(0)
        else:
            mask_t = None

        with torch.no_grad():
            probs = self.actor(state_t, mask_t)

        dist   = torch.distributions.Categorical(probs)
        action = dist.sample()
        return action.item(), dist.log_prob(action).item()

    def store(self, state, action, reward, mask):
        """Store one transition."""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.masks.append(mask)

    def compute_returns(self, next_value, gamma):
        """
        Compute discounted returns R_t (Eq. 27).
        R_t = sum(gamma^i * r_{t+i}) + gamma^k * V(s_{t+k})
        """
        returns = []
        R = next_value
        for r in reversed(self.rewards):
            R = r + gamma * R
            returns.insert(0, R)
        return returns

    def update(self, next_state=None):
        """
        Update actor and critic networks.
        L = L_pi + c1*L_V - c2*H(pi)
        """
        if len(self.states) == 0:
            return None, None

        # ── Compute next state value ──────────────────────────
        if next_state is not None:
            ns_t = torch.FloatTensor(next_state).unsqueeze(0)
            with torch.no_grad():
                next_value = self.critic(ns_t).item()
        else:
            next_value = 0.0

        returns = self.compute_returns(next_value, self.gamma)

        # ── Convert to tensors ────────────────────────────────
        states_t  = torch.FloatTensor(np.array(self.states))
        actions_t = torch.LongTensor(self.actions)
        returns_t = torch.FloatTensor(returns)

        # Stack masks
        if self.masks[0] is not None:
            masks_t = torch.stack(self.masks)
        else:
            masks_t = None

        # ── Critic loss L_V (Eq. 28) ──────────────────────────
        values      = self.critic(states_t).squeeze()
        advantages  = returns_t - values.detach()
        critic_loss = F.mse_loss(values, returns_t)

        # ── Actor loss L_pi (Eq. 26) ──────────────────────────
        probs    = self.actor(states_t, masks_t)
        dist     = torch.distributions.Categorical(probs)
        log_prob = dist.log_prob(actions_t)
        entropy  = dist.entropy().mean()

        actor_loss = -(log_prob * advantages).mean() \
                     - self.c2 * entropy

        # ── Update networks ───────────────────────────────────
        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        self.actor_optimizer.step()

        self.critic_optimizer.zero_grad()
        (self.c1 * critic_loss).backward()
        self.critic_optimizer.step()

        # ── Clear buffer ──────────────────────────────────────
        self.states   = []
        self.actions  = []
        self.rewards  = []
        self.masks    = []
        self.log_probs = []

        return actor_loss.item(), critic_loss.item()

    def save(self, path):
        torch.save({
            'actor' : self.actor.state_dict(),
            'critic': self.critic.state_dict()
        }, path)

    def load(self, path):
        ckpt = torch.load(path, map_location='cpu')
        self.actor.load_state_dict(ckpt['actor'])
        self.critic.load_state_dict(ckpt['critic'])

    def __repr__(self):
        return (f"A3CAgent | state={self.state_dim} | "
                f"action={self.action_dim} | "
                f"gamma={self.gamma} | "
                f"c1={self.c1} | c2={self.c2}")


if __name__ == "__main__":
    torch.manual_seed(42)
    np.random.seed(42)

    agent = A3CAgent(state_dim=20, action_dim=7)
    print("=== Sprint 8: A3C Agent Verification ===")
    print(f"\n{agent}")

    # ── Test 1: Network shapes ────────────────────────────────
    print("\n--- Network architecture ---")
    state = np.random.rand(20).astype(np.float32)
    s_t   = torch.FloatTensor(state).unsqueeze(0)
    probs  = agent.actor(s_t)
    value  = agent.critic(s_t)
    print(f"Actor  input:  {s_t.shape}")
    print(f"Actor  output: {probs.shape}  (7 action probs)")
    print(f"Critic output: {value.shape}  (1 value)")
    print(f"Action probs sum: {probs.sum().item():.6f} (expect 1.0)")

    # ── Test 2: Action masking ────────────────────────────────
    print("\n--- Action masking test ---")
    mask = agent.build_mask(current_rsu_id=3)
    print(f"Mask (RSU 3 masked): {mask.tolist()}")
    probs_masked = agent.actor(s_t, mask.unsqueeze(0))
    print(f"Prob of action 3: {probs_masked[0][3].item():.6f} "
          f"(expect 0.0)")
    print(f"Probs sum: {probs_masked.sum().item():.6f}")

    # ── Test 3: Action selection ──────────────────────────────
    print("\n--- Action selection ---")
    for _ in range(5):
        action, log_p = agent.select_action(state, mask)
        print(f"  action={action}, log_prob={log_p:.4f}")

    # ── Test 4: Update ────────────────────────────────────────
    print("\n--- Training update test ---")
    for i in range(10):
        s   = np.random.rand(20).astype(np.float32)
        m   = agent.build_mask(current_rsu_id=1)
        a, lp = agent.select_action(s, m)
        r   = np.random.randn()
        agent.store(s, a, r, m)

    actor_loss, critic_loss = agent.update(
        next_state=np.random.rand(20).astype(np.float32))
    print(f"Actor loss:  {actor_loss:.4f}")
    print(f"Critic loss: {critic_loss:.4f}")
    print(f"Buffer cleared: {len(agent.states) == 0}")

    # ── Test 5: Save and load ─────────────────────────────────
    print("\n--- Save/Load test ---")
    agent.save("test_agent.pt")
    agent2 = A3CAgent(state_dim=20, action_dim=7)
    agent2.load("test_agent.pt")
    
    # Compare post-update weights, not pre-update
    probs_after = agent.actor(s_t)   # agent after update
    probs2 = agent2.actor(s_t)
    print(f"Loaded agent probs match: "
          f"{torch.allclose(probs_after, probs2)}")

    print("\nSprint 8 complete.")