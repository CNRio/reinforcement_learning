# coding: utf-8

"""
Solve the cart pole task with q-table learning
Ref:
https://lilianweng.github.io/lil-log/2018/05/05/implementing-deep-reinforcement-learning-models.html
"""

import os
import time
import gym
import numpy as np
from gym.spaces import Box, Discrete
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import traceback
import pandas as pd


def plot_learning_curve(filepath, value_dict, xlabel='step'):
    fig = plt.figure(figsize=(12, 4 * len(value_dict)))
    for i, (key, values) in enumerate(value_dict.items()):
        ax = fig.add_subplot(len(value_dict), 1, i + 1)
        ax.plot(range(len(values)), values)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(key)
        ax.grid('k--', alpha=0.6)
    plt.tight_layout()
    plt.savefig(filepath)


class DiscretizedObservationWrapper(gym.ObservationWrapper):
    def __init__(self, env, n_bins=10, low=None, high=None):
        super(DiscretizedObservationWrapper, self).__init__(env)
        assert isinstance(env.observation_space, Box)

        low = self.observation_space.low if low is None else low
        high = self.observation_space.high if high is None else high

        low = np.array(low)
        high = np.array(high)

        self.n_bins = n_bins
        self.val_bins = [np.linspace(l, h, n_bins + 1) for l, h in
                         zip(low.flatten(), high.flatten())]
        self.ob_shape = self.observation_space.shape
        # the actual #bins per dimension is self.n_bins + 2, counting the left and right outliers
        self.observation_space = Discrete((n_bins + 2) ** len(low))

    def _convert_to_one_number(self, digits):
        return sum([d * ((self.n_bins + 2) ** i) for i, d in enumerate(digits)])

    def observation(self, observation):
        digits = [np.digitize([x], bins)[0]
                  for x, bins in zip(observation.flatten(), self.val_bins)]
        return self._convert_to_one_number(digits)


class QLearnPolicy(object):
    def __init__(self, env,
                 gamma=0.99,
                 alpha=0.5,
                 alpha_decay=0.998,
                 epsilon=1.0,
                 epsilon_final=0.05):
        assert isinstance(env.action_space, Discrete)
        assert isinstance(env.observation_space, Discrete)
        
        self.env = env
        self.gamma = gamma
        self.alpha = alpha
        self.alpha_decay = alpha_decay
        self.epsilon = epsilon
        self.epsilon_final = epsilon_final

        self.n_actions = self.env.action_space.n
        self.n_states = self.env.observation_space.n
        self.actions = range(self.n_actions)

        self.Q = np.zeros(shape=(self.n_states, self.n_actions), dtype=np.float32)

    def act(self, state, training):
        """Pick best action according to Q values ~ argmax_a Q(s, a).
        Exploration is forced by epsilon-greedy.
        """
        if training and self.epsilon > 0. and np.random.rand() < self.epsilon:
            return self.env.action_space.sample()

        # Pick the action with highest Q value
        max_q = np.max(self.Q[state, :])
        actions_with_max_q = np.arange(self.n_actions)[self.Q[state, :] == max_q]
        return np.random.choice(actions_with_max_q)
    
    def _update_q_value(self, state, action, new_state, reward, done):
        """
        Q(s, a) += alpha * (r(s, a) + gamma * max Q(s', .) - Q(s, a))
        """
        if done:
            self.Q[state, action] += self.alpha * (reward - self.Q[state, action])
        else:
            max_q_next = np.max(self.Q[new_state, :])
            self.Q[state, action] += self.alpha * (reward + self.gamma * max_q_next - self.Q[state, action])

    def train(self, n_episodes, result_path='./', every_episodes=None):
        reward_history = []
        reward_averaged = []
        epsilon_drop = (self.epsilon - self.epsilon_final) / n_episodes
        step = 0
        for episode in xrange(n_episodes):
            state = self.env.reset()
            reward_episode = 0.
            while True:
                action = self.act(state, training=True)
                new_state, reward, done, _ = self.env.step(action)
                try:
                    self._update_q_value(state, action, new_state, reward, done)
                except:
                    print state, action, new_state, reward, done
                    raise Exception(traceback.format_exc())
                step += 1
                reward_episode += reward
                state = new_state
                if done:
                    break
            reward_history.append(reward_episode)
            reward_averaged.append(np.mean(reward_history[-50:]))
            self.alpha *= self.alpha_decay
            if self.epsilon > self.epsilon_final:
                self.epsilon -= epsilon_drop

            if every_episodes is not None and episode % every_episodes == 0:
                print("[episode:{e} | step:{s}] best: {b} avg: {a:.4f}|{h} alpha: {al:.4f} epsilon: {ep:.4f}".format(
                    e=episode, s=step,
                    b=np.max(reward_history), a=np.mean(reward_history[-10:]), h=reward_history[-5:],
                    al=self.alpha, ep=self.epsilon))
        print("Training completed. #episodes: {n}, Max reward: {m}, Average reward: {a}".format(
            n=len(reward_history), m=np.max(reward_history), a=np.mean(reward_history)))
            
        if not os.path.exists(result_path):
            os.makedirs(result_path)
        fig_file = os.path.join(result_path, 'QLearnPolicy-{t}.png'.format(t=int(time.time())))
        plot_learning_curve(fig_file,
                            {'reward': reward_history, 'reward_avg50': reward_averaged},
                            xlabel='episode')

    def evaluate(self, n_episodes):
        reward_history = []
        for episode in xrange(n_episodes):
            state = self.env.reset()
            reward_episode = 0.
            while True:
                action = self.act(state, training=False)
                new_state, reward, done, _ = self.env.step(action)
                reward_episode += reward
                state = new_state
                if done:
                    break
            reward_history.append(reward_episode)
        return reward_history


if __name__ == '__main__':
    env = DiscretizedObservationWrapper(
        gym.make("CartPole-v0"),
        n_bins=8,
        low=[-2.4, -2.0, -0.42, -3.5],
        high=[2.4, 2.0, 0.42, 3.5])
    n_episodes_train = 1000
    n_episodes_eval = 100

    policy = QLearnPolicy(env=env)
    policy.train(n_episodes=n_episodes_train, every_episodes=10, result_path='result')
    reward_history = policy.evaluate(n_episodes=n_episodes_eval)
    print 'reward history over {e} episodes: avg: {a:.4f}'.format(e=n_episodes_eval, a=np.mean(reward_history))
    print pd.Series(reward_history).describe()