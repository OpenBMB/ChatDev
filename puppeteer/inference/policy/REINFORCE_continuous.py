import torch
import atexit
import os
import datetime
import json
import numpy as np
import torch.nn as nn
import yaml
import logging
from utils.other_utils import Singleton
from inference.policy.base_policy import LLMPolicy, LearningPolicy
from model.embedding import RewardModelTokenRepresentation

global_config = yaml.safe_load(open("./config/global.yaml", "r"))
logger = logging.getLogger("train")

@Singleton
class MLP_PolicyNetwork(nn.Module):
    def __init__(self, input_dim, output_dim):
        super().__init__()
        self.fc1 = torch.nn.Linear(input_dim, 512)
        self.fc2 = torch.nn.Linear(512, 128)
        self.fc3 = torch.nn.Linear(128, 32)
        self.fc4 = torch.nn.Linear(32, output_dim)
        self.relu = torch.nn.ReLU()
        self.softmax = torch.nn.Softmax(dim=1)
        self.input_dim = input_dim
        self.output_dim = output_dim
    
    def forward(self, x):
        x = x.to(torch.float32)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        x = self.relu(x)
        x = self.fc3(x)
        x = self.relu(x)
        x = self.fc4(x)
        x = self.softmax(x)
        return x


@Singleton
class ContinuousREINFORCE(LearningPolicy):
    def __init__(self, agent_graph, action_graph, config_path="config/policy.json"):
        super().__init__(agent_graph, action_graph)
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Set parameters from config
        self.device = self.config["device"]["type"]
        
        # Training parameters
        self.model_path = self.config["paths"]["model_path"]
        self.training = self.config["training"]["training"]
        self.loading = self.config["training"]["loading"]
        self.learning_rate = self.config["training"]["learning_rate"]
        self.gamma = self.config["training"]["gamma"]
        self.sample_size = self.config["training"]["sample_size"]
        self.lambda_kl_loss = self.config["training"]["lambda_kl_loss"]

        # Agent parameters
        self.max_num_agents = self.config["agent"]["max_num_agents"] 
        self.next_num_agents = self.config["agent"]["next_num_agents"] 
        self.max_path = self.config["agent"]["max_path"]
        self.threshold = self.config["agent"]["threshold"]
        
        # LLM parameters
        self.llm_prior = self.config["llm"]["prior"]
        self.llm_prior_redistribution = self.config["llm"]["prior_redistribution"]
        self.redistribution_weight = self.config["llm"]["redistribution_weight"]
        
        # Initialize state representation and policy network
        self.state_representation = RewardModelTokenRepresentation()
        self.policy_network = MLP_PolicyNetwork(self.state_representation.dim, self.actions_dim) 
        self.policy_network = self.policy_network.to(self.device) 
        if not self.training:
            self.load_model(self.get_latest_model_path())
        if self.loading:
            self.load_model(self.model_path)

        # Agent setup
        self.agent_hash_list = agent_graph.hash_nodes
        self.agent_role_list = agent_graph.role_nodes
        
        # Initialize tracking variables
        self.executed_trajectories = []
        self.execution_count = 0 
        self.current_trajectories = []
        self.current_trajectory_idx = 0
        
        self.policy_losses = []
        self.rewards_history = []
        self.action_probs_history = []
        self.llm_action_probs_history = []
        self.reward_from_rm = []
        self.accumulated_acc = []
        self.entropy_history = []

        # Setup actions and rewards
        self.end_action = torch.tensor(self.agent_graph.terminator_agent_index, device=self.device)
        self.web_actions = torch.tensor(self.agent_graph.search_agent_indices, device=self.device)
        
        # Initialize reward factors from config
        reward_factors = self.config["agent"]["reward_factors"]
        self.agent_reward_factor = [reward_factors["default"]] * self.actions_dim
        self.agent_reward_factor[self.end_action.item()] = reward_factors["terminator"]
        for web_idx in self.web_actions:
            self.agent_reward_factor[web_idx.item()] = reward_factors["web_search"]

        self.current_task = None
        self.previous_task = None
        self.global_step = 0    
        self.prob_step=0
        
        # Initialize optimizer
        self.optimizer = torch.optim.Adam(self.policy_network.parameters(), lr=self.learning_rate)
        self.max_step_num = global_config.get("graph").get("max_step_num")
        self.llm_policy = LLMPolicy(self.agent_graph, self.action_graph)
        
        atexit.register(self.save_model)

    def logarithmic_cost(self, step):
        """Calculate logarithmic cost using config parameters"""
        scale = self.config["cost"]["scale"]
        growth_rate = self.config["cost"]["growth_rate"]
        # Normalize step to [0,1] range
        normalized_step = (step + 1) / (self.max_step_num + 1)

        if self.config["cost"]["inverse"]:
            step_cost = scale * (1 - torch.log(torch.tensor(1 + growth_rate * normalized_step, device=self.device)) 
                            / torch.log(torch.tensor(1 + growth_rate, device=self.device)))
        else:
            step_cost = scale * (torch.log(torch.tensor(1 + growth_rate * normalized_step, device=self.device)) 
                            / torch.log(torch.tensor(1 + growth_rate, device=self.device)))
        print("\033[1;33mstep cost: {}\033[0m".format(step_cost))
        return step_cost

    def save_model(self, path=None, tag=None):
        """Save model with config"""
        path = self.config["paths"]["checkpoint_path"]

        os.makedirs(path, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'policy_net_{timestamp}' + (f'_{tag}' if tag else '') + '.pt'
        save_path = os.path.join(path, filename)
        
        checkpoint = {
            'model_state_dict': self.policy_network.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict() if hasattr(self, 'optimizer') else None,
            'input_dim': self.policy_network.input_dim,
            'output_dim': self.policy_network.output_dim,
            'timestamp': timestamp,
            'config': self.config,  # Save the config with the model
            'metadata': {
                'tag': tag,
                'version': '1.0',
            }
        }
        
        try:
            torch.save(checkpoint, save_path)
            print(f"Model saved successfully to {save_path}")
            return save_path
            
        except Exception as e:
            print(f"Error saving model: {str(e)}")
            return None

    def update_executed_trajectories(self):
        if self.current_task != self.previous_task:
            self.previous_task = self.current_task
            self.execution_count += 1
            num_to_add = self.execution_count - len(self.executed_trajectories) 
            if num_to_add > 0:
                self.executed_trajectories.extend([[] for _ in range(num_to_add)])
        self.current_trajectories = self.executed_trajectories[self.execution_count-1]
    
    def init_forward(self, global_info):
        print("\033[1;33mInit Policy Forward\033[0m")
        logger.info("[Init Policy Forward]")
        self.current_task = global_info.task    
        self.update_executed_trajectories()
        
        state, rew = self.get_state_representation(global_info)  
        action_probs = self.policy_network(state) #shape (1,action_dim)

        self.action_probs_history.append(action_probs.T.squeeze(1))
        self.reward_from_rm.append(rew)
        logger.info("Action probs: {}".format(action_probs))
        
        entropy = -(action_probs * torch.log(action_probs + 1e-10)).sum()
        self.entropy_history.append(entropy)
        m = torch.distributions.Categorical(action_probs)
        agent_indices = self.select_agents_by_threshold(action_probs).T.squeeze(1)

        self.current_trajectory_idx = 0
        length = len(self.current_trajectories) + agent_indices.shape[0]
        while len(self.current_trajectories) < length:
            self.current_trajectories.append([])

        for i, agent_idx in enumerate(agent_indices):
            prob_value = action_probs[0, agent_idx.item()]
            if i == 0:
                self.append_to_trajectory(self.current_trajectory_idx, agent_idx, prob_value, global_info, None, m, rew)
            else:
                trajectory_idx = len(self.current_trajectories) - len(agent_indices) + i
                self.append_to_trajectory(trajectory_idx, agent_idx, prob_value, global_info, None, m, rew)
        return agent_indices

    def iter_forward(self, global_info):
        print("\033[1;33mFollowing Policy Forward\033[0m")
        logger.info("Following Policy Forward")

        self.current_task = global_info.task    
        if self.llm_prior:
            prior_action_probs = self.llm_policy.forward_prior(global_info)
        else:
            prior_action_probs = None
        print("Prior action probs: {}".format(prior_action_probs))
        logger.info("Prior action probs: {}".format(prior_action_probs))

        state, rew = self.get_state_representation(global_info)  
        action_probs = self.policy_network(state) #shape (1,action_dim)
        
        if self.llm_prior_redistribution:
            action_probs = (1 - self.redistribution_weight) * action_probs + \
                            self.redistribution_weight * prior_action_probs

            action_probs /= action_probs.sum()
        self.action_probs_history.append(action_probs.T.squeeze(1))
        self.reward_from_rm.append(rew)
        logger.info("Action probs: {}".format(action_probs))
        
        entropy = -(action_probs * torch.log(action_probs + 1e-10)).sum()
        self.entropy_history.append(entropy)
        m = torch.distributions.Categorical(action_probs)
        agent_indices = self.select_agents_by_threshold(action_probs).T.squeeze(1)
    
        self.current_trajectory_idx = global_info.path_id 
        length = len(self.current_trajectories) + len(agent_indices) - 1
        original_length = len(self.current_trajectories)
        while len(self.current_trajectories) < length:
            self.current_trajectories.append([])

        for i, agent_idx in enumerate(agent_indices):
            prob_value = action_probs[0, agent_idx.item()]
            if i == 0:
                self.append_to_trajectory(self.current_trajectory_idx, agent_idx, prob_value, global_info, prior_action_probs, m, rew)
            else:
                trajectory_idx = original_length + i - 1
                self.current_trajectories[trajectory_idx] = self.clone_trajectory(self.current_trajectory_idx)
                self.append_to_trajectory(trajectory_idx, agent_idx, prob_value, global_info, prior_action_probs, m, rew)
        return agent_indices

    def append_to_trajectory(self, trajectory_idx, agent_idx, prob_value, global_info, prior_action_probs, m, rew=0):
        cost = self.logarithmic_cost(len(self.current_trajectories[trajectory_idx])) * self.agent_reward_factor[agent_idx.item()]
        self.current_trajectories[trajectory_idx].append({
            'prob': prob_value,
            'log_prob': m.log_prob(agent_idx),
            'state_identifier': global_info.workflow.state,
            'action': self.agent_role_list[agent_idx.item()],
            'reward': cost,
            'reward_model': rew,
            'prior_prob': prior_action_probs[agent_idx.item()] if prior_action_probs is not None else None
        })
        print(trajectory_idx, self.current_trajectories[trajectory_idx])

    def clone_trajectory(self, source_idx):
            return [{
                'prob': t['prob'].clone(),
                'log_prob': t['log_prob'].clone(),
                'state_identifier': t['state_identifier'],
                'action': t['action'],
                'reward': t['reward'],
                'reward_model': t['reward_model'],
                'prior_prob': t['prior_prob'].clone() if t['prior_prob'] is not None else None
            } for t in self.current_trajectories[source_idx][:-1]]
    
    def forward(self, global_info):
        if global_info.path_id == -1:
            agent_indices = self.init_forward(global_info)
        else:
            agent_indices = self.iter_forward(global_info)
        print("Agent Indices: {}".format(agent_indices))
        selected_agents = [self.agent_hash_list[i] for i in agent_indices]
        return  selected_agents
    
    def calculate_returns(self, trajectory):
        returns = []
        R = 0
        for t in reversed(trajectory):
            R = t.get('reward', 0) + self.gamma * R 
            returns.insert(0, R)
        return torch.tensor(returns, device=self.device)
    
    def get_state_representation(self, global_info):
        role_list = global_info.agent_role_list()
        print(role_list)
        state_context = self.agent_graph.get_agent_dialog_history(role_list, question=global_info.task.get("Question"))
        print(state_context)
        print(type(state_context))
        state, reward = self.state_representation(state_context)
        print(state, reward)
        return state, reward        
    
    def update(self):
        logger.info("Update")   
        logger.info("Executed trajectories: {}".format(self.executed_trajectories))
        if not self.training:
            metrics = {
            'reasoning/action_probs': torch.sum(torch.stack(self.action_probs_history), dim=0),
            "training/entropy": np.mean([e.detach().cpu().item() for e in self.entropy_history])
            }
            logger.info("metrics: {}".format(metrics))  
            self.current_trajectories = []
            self.executed_trajectories = []
            self.entropy_history = []
            self.execution_count = 0
            return {}
        if len(self.executed_trajectories) >= self.sample_size:
            episode_returns = []
            episode_lengths = []
            episode_last_rewards = []
            episode_acc = []
            episode_tokens = []
            episode_cost = []
            episode_metrics = {}
            kl_losses = []
            logger.info("Update with sample size {}".format(self.sample_size))
            policy_loss = []
            episode_loss = []
            for trajectories in self.executed_trajectories[:self.sample_size]:
                task_avg_length = []
                task_avg_reward = []
                task_last_reward = []   
                task_acc = []
                task_avg_tokens = []
                task_avg_cost = []
                task_avg_metrics = []
                for trajectory in trajectories:
                    if trajectory[-1].get('finalized', False):
                        logger.info("Trajectory: {}".format(trajectory))
                        returns = self.calculate_returns(trajectory)
                        # episode_returns.append(sum(returns))
                        task_avg_reward.append(sum(returns))
                        task_avg_length.append(len(trajectory))
                        task_last_reward.append(trajectory[-1].get('reward', 0))
                        task_avg_tokens.append(trajectory[-1].get('total_tokens', 0))
                        task_avg_cost.append(trajectory[-1].get('total_cost', 0))
                        task_avg_metrics.append(trajectory[-1].get('metrics', {}))
                        if task_last_reward[-1] > 0:
                            task_acc.append(1)
                        else:
                            task_acc.append(0)
                        # task_acc.append(task_last_reward[-1].cpu().item())
                        # episode_lengths.append(len(trajectory))
                        print("returns: {}".format(returns))
                        logger.info("Trajectory returns: {}".format(returns))
                        
                        for t, R in zip(trajectory, returns):
                            if t.get('prob', None) is not None and t.get('prior_prob', None) is not None:
                                kl_loss = t.get('prior_prob', 0) * torch.log(t['prior_prob'] / (t['prob']+1e-10))
                                logger.info("Add KL loss: {}".format(kl_loss))
                            else: 
                                kl_loss = 0
                                logger.info("No KL loss: {}".format(kl_loss))
                            kl_loss = torch.tensor(kl_loss).to(self.device)
                            kl_losses.append(kl_loss)
                            loss = (-t['log_prob'] * R + self.lambda_kl_loss * kl_loss).to(self.device)
                            
                            if loss.dim() == 0:  # scalar loss, convert to shape [1]
                                loss = loss.view(1)
                            elif loss.dim() == 1:  # already [1], keep it
                                pass
                            policy_loss.append(loss)
                            logger.info("loss for one sample: {}".format(policy_loss))
                if len(task_avg_length) == 0:
                    continue
                else:
                    episode_lengths.append(sum(task_avg_length)/len(task_avg_length))
                if len(task_avg_reward) == 0:
                    continue
                else:
                    episode_returns.append(sum(task_avg_reward)/len(task_avg_reward))
                if len(task_last_reward) == 0:
                    continue
                else:
                    episode_last_rewards.append(sum(task_last_reward)/len(task_last_reward))
                if len(task_avg_tokens) == 0:
                    continue
                else:  
                    episode_tokens.append(sum(task_avg_tokens)/len(task_avg_tokens))
                if len(task_avg_cost) == 0:
                    continue
                else:
                    episode_cost.append(sum(task_avg_cost)/len(task_avg_cost))
                if len(task_acc) == 0:
                    continue
                else:
                    episode_acc.append(sum(task_acc)/len(task_acc))
                if len(task_avg_metrics) == 0:
                    continue    
                elif task_avg_metrics[0] == {}:
                    continue
                else:
                    for key in task_avg_metrics[0].keys():
                        if key not in episode_metrics:
                            episode_metrics[key] = []
                        episode_metrics[key].append(sum([m[key] for m in task_avg_metrics])/len(task_avg_metrics))
                    

            if policy_loss: 
                logger.info("Policy loss: {}".format(policy_loss))
                policy_loss = torch.stack(policy_loss).sum()/(self.sample_size)
                logger.info("Policy loss stack: {}".format(policy_loss))
                policy_loss -= sum(self.entropy_history)
                logger.info("Policy loss with entropy: {}".format(policy_loss))
                self.optimizer.zero_grad()
                policy_loss.backward()
                self.optimizer.step()
                metrics = {
                    'reasoning/action_probs': torch.sum(torch.stack(self.action_probs_history), dim=0),
                    'reasoning/reward_from_rm': sum(self.reward_from_rm),
                    'reasoning/acc': np.mean([a for a in episode_acc]),
                    'reasoning/tokens': np.mean([t for t in episode_tokens]),
                    'reasoning/cost': np.mean([c for c in episode_cost]),
                    'training/policy_loss': policy_loss.item(),
                    'reasoning/mean_return': np.mean([r.detach().cpu().item() for r in episode_returns]),
                    'reasoning/mean_episode_length': np.mean(episode_lengths),
                    'reasoning/mean_last_reward': np.mean([r.detach().cpu().item() for r in episode_last_rewards]),
                    'training/mean_kl_loss': np.mean([kl.detach().cpu().item() for kl in kl_losses]),
                    "training/entropy": np.mean([e.detach().cpu().item() for e in self.entropy_history]),
                }
                metrics.update({f'reasoning/{key}': np.mean([r.cpu().item() for r in episode_metrics[key]]) for key in episode_metrics})
                logger.info("metrics: {}".format(metrics))  
                self.global_step += 1
                self.policy_losses.append(policy_loss.item())
                self.current_trajectories = []
                self.executed_trajectories = []
                self.entropy_history = []
                self.execution_count = 0
                self.reward_from_rm = []
                self.action_probs_history = []
                self.llm_action_probs_history = []
                return {
                    'policy_loss': policy_loss.item(),
                    'mean_reward': torch.tensor(returns, device=self.device).mean().item()
                }
        return {}
    
    def finalize_task(self, transition, global_info):
        print("\033[1;33mtransition reward: {}\033[0m".format(transition.get('reward', 0)))
        self.current_trajectories = self.executed_trajectories[self.execution_count-1]
        idx = transition.get('path_id', 0)
        if self.current_trajectories and idx < len(self.current_trajectories):
            state, rew = self.get_state_representation(global_info)
            action_probs = self.policy_network(state)
            prob_value = action_probs[0, self.end_action.item()]
            m = torch.distributions.Categorical(action_probs)
            current_trajectory = self.current_trajectories[idx]
            for index, action in  enumerate(global_info.workflow.workflow):
                cost = action.cost
                print("\033[1;33mtoken cost: {}\033[0m".format(cost))
                print("\033[1;33mcost factor: {}\033[0m".format(cost/100000))
                current_trajectory[index]["reward"] *= cost/100000 
                print("\033[1;33mReward: {}\033[0m".format(current_trajectory[index]['reward']))
            if current_trajectory: 
                step_reward = self.logarithmic_cost(len(current_trajectory))
                total_tokens = global_info.total_tokens
                total_cost = global_info.total_cost
                if transition.get('reward', 0) > 0: 
                    reward = transition.get('reward', 0) + self.agent_reward_factor[self.end_action.item()] * step_reward
                else:
                    reward = transition.get('reward', 0) - self.agent_reward_factor[self.end_action.item()] * step_reward
                
                if current_trajectory[-1].get("action") == self.agent_role_list[self.end_action.item()]:
                    current_trajectory[-1]["reward"] = reward
                    current_trajectory[-1]['total_tokens'] = total_tokens
                    current_trajectory[-1]['total_cost'] = total_cost
                    current_trajectory[-1]['finalized'] = True
                    current_trajectory[-1]['reward_model'] = rew
                    current_trajectory[-1]['metrics'] = transition.get('metrics', {})
                    print("\033[1;33mLast Reward: {}\033[0m".format(current_trajectory[-1]['reward']))
                else:
                    current_trajectory.append({
                        'prob': prob_value,
                        'log_prob': m.log_prob(self.end_action),
                        'state_identifier': transition.get('state', global_info.workflow.state),
                        'action': self.agent_role_list[self.end_action.item()],
                        'reward': reward,
                        'reward_model': rew,
                        'finalized': True,
                        'total_tokens': total_tokens,
                        'total_cost': total_cost,
                        'metrics': transition.get('metrics', {})
                    })
                    print("\033[1;33mLast Reward: {}\033[0m".format(current_trajectory[-1]['reward']))
        self.rewards_history.append(transition.get('reward', 0))
        
    
    def select_agents_by_probability(self, action_probs):
        num_agents_to_select = torch.randint(1, self.max_num_agents+1, (1,)).item()
        selected_indices = torch.multinomial(action_probs, num_agents_to_select, replacement=False)
        return selected_indices

    def select_agents_by_threshold(self, action_probs, threshold=0.1):
        threshold = 2/self.agent_graph.num
        selected_indices = torch.nonzero(action_probs[0] > threshold).squeeze(1)
        if len(selected_indices) == 0:
            num_to_select = min(self.max_path, self.max_num_agents)
            selected_indices = torch.multinomial(action_probs, num_to_select, replacement=False)
            return selected_indices
        else:
            probs = action_probs[0][selected_indices]
            sorted_idx = torch.argsort(probs, descending=True)
            selected_indices = selected_indices[sorted_idx]
            
            num_agents_to_select = min(len(selected_indices), self.max_path, self.max_num_agents)
            selected_indices = selected_indices[:num_agents_to_select]
            
        return selected_indices.unsqueeze(0)
    
    def load_model(self, path, strict=True):
        try:
            if not os.path.exists(path):
                logger.error(f"Model file not found: {path}")
                return False
            
            checkpoint = torch.load(path, map_location=self.device)
            
            # Validate model architecture
            if (checkpoint['input_dim'] != self.policy_network.input_dim or 
                checkpoint['output_dim'] != self.policy_network.output_dim):
                if strict:
                    raise ValueError(f"Model architecture mismatch. Expected input_dim={self.policy_network.input_dim}, "
                                  f"output_dim={self.policy_network.output_dim} but got input_dim={checkpoint['input_dim']}, "
                                  f"output_dim={checkpoint['output_dim']}")
                logger.warning("Model architecture mismatch, but continuing due to non-strict mode")
            
            # Load model state
            self.policy_network.load_state_dict(checkpoint['model_state_dict'], strict=strict)
            self.policy_network = self.policy_network.to(self.device)
            
            # Load optimizer state if available
            if checkpoint['optimizer_state_dict'] and hasattr(self, 'optimizer'):
                self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
                # Move optimizer state to correct device
                for state in self.optimizer.state.values():
                    for k, v in state.items():
                        if isinstance(v, torch.Tensor):
                            state[k] = v.to(self.device)
            
            # Load config if available
            if 'config' in checkpoint:
                # Merge loaded config with current config, prioritizing current config
                self.config.update({k: v for k, v in checkpoint['config'].items() 
                                  if k not in self.config})
            
            logger.info(f"Model loaded successfully from {path}")
            logger.info(f"Model timestamp: {checkpoint['timestamp']}")
            if checkpoint['metadata'].get('tag'):
                logger.info(f"Model tag: {checkpoint['metadata']['tag']}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return False

    def get_latest_model_path(self):
        """Get the path of the latest model checkpoint"""
        try:
            path = self.model_path
            if os.path.exists(path) and os.path.isfile(path):
                return path
            
            path = self.config["paths"]["checkpoint_path"]
            if not os.path.exists(path):
                return None

            model_files = [f for f in os.listdir(path) if f.endswith('.pt')]
            if not model_files:
                return None
            
            latest_model = max(model_files, key=lambda x: os.path.getctime(os.path.join(path, x)))
            return os.path.join(path, latest_model)
            
        except Exception as e:
            print(f"Error finding latest model: {str(e)}")
            return None
    