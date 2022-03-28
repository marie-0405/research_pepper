#!/usr/bin/env python
'''
    By Miguel Angel Rodriguez <duckfrost@theconstructsim.com>
    Visit our website at www.theconstructsim.com
'''
import gym
import rospy
import numpy as np
import time
from gym import utils, spaces
from geometry_msgs.msg import Pose
from gym.utils import seeding
from gym.envs.registration import register
from gazebo_connection import GazeboConnection
from joint_publisher import JointPub
from pepper_state import PepperState
from controllers_connection import ControllersConnection

#register the training environment in the gym as an available one
reg = register(
    id='Pepper-v0',
    entry_point='pepper_env:PepperEnv',
    timestep_limit=100000,
    )


class PepperEnv(gym.Env):

    def __init__(self):
        
        # We assume that a ROS node has already been created
        # before initialising the environment

        # gets training parameters from param server
        self.desired_length = Pose()
        self.desired_length.position.x = rospy.get_param("/desired_length/x")
        self.desired_length.position.y = rospy.get_param("/desired_length/y")
        self.desired_length.position.z = rospy.get_param("/desired_length/z")
        self.running_step = rospy.get_param("/running_step")
        self.min_distance = rospy.get_param("/min_distance")
        self.max_distance = rospy.get_param("/max_distance")
        self.joint_increment_value = rospy.get_param("/joint_increment_value")
        self.done_reward = rospy.get_param("/done_reward")
        self.alive_reward = rospy.get_param("/alive_reward")

        self.list_of_observations = rospy.get_param("/list_of_observations")

        r_shoulder_pitch_max = rospy.get_param("/joint_limits_array/r_shoulder_pitch_max")
        r_shoulder_pitch_min = rospy.get_param("/joint_limits_array/r_shoulder_pitch_min")
        r_shoulder_roll_max = rospy.get_param("/joint_limits_array/r_shoulder_roll_max")
        r_shoulder_roll_min = rospy.get_param("/joint_limits_array/r_shoulder_roll_min")
        r_elbow_roll_max = rospy.get_param("/joint_limits_array/r_elbow_roll_max")
        r_elbow_roll_min = rospy.get_param("/joint_limits_array/r_elbow_roll_min")
        r_elbow_yaw_max = rospy.get_param("/joint_limits_array/r_elbow_yaw_max")
        r_elbow_yaw_min = rospy.get_param("/joint_limits_array/r_elbow_yaw_min")
        r_wrist_yaw_max = rospy.get_param("/joint_limits_array/r_wrist_yaw_max")
        r_wrist_yaw_min = rospy.get_param("/joint_limits_array/r_wrist_yaw_min")

        self.joint_limits = {"rsp_max": r_shoulder_pitch_max,
                             "rsp_min": r_shoulder_pitch_min,
                             "rsr_max": r_shoulder_roll_max,
                             "rsr_min": r_shoulder_roll_min,
                             "rer_max": r_elbow_roll_max,
                             "rer_min": r_elbow_roll_min,
                             "rey_max": r_elbow_yaw_max,
                             "rey_min": r_elbow_yaw_min,
                             "rwy_max": r_wrist_yaw_max,
                             "rwy_min": r_wrist_yaw_min,
                             }

        self.discrete_division = rospy.get_param("/discrete_division")  # ?

        self.maximum_base_linear_acceleration = rospy.get_param("/maximum_base_linear_acceleration")  # ?
        self.maximum_base_angular_velocity = rospy.get_param("/maximum_base_angular_velocity")  # ?
        self.maximum_joint_effort = rospy.get_param("/maximum_joint_effort")  # ?

        self.weight_r1 = rospy.get_param("/weight_r1")
        self.weight_r2 = rospy.get_param("/weight_r2")

        r_shoulder_pitch_init_value = rospy.get_param("/init_joint_pose/r_shoulder_pitch")
        r_shoulder_pitch_init_value = rospy.get_param("/init_joint_pose/r_shoulder_roll")
        r_elbow_roll_init_value = rospy.get_param("/init_joint_pose/r_elbow_roll")
        r_elbow_yaw_init_value = rospy.get_param("/init_joint_pose/r_elbow_yaw")
        r_wrist_yaw_init_value = rospy.get_param("/init_joint_pose/r_wrist_yaw")
        self.init_joint_pose = [r_shoulder_pitch_init_value,r_shoulder_pitch_init_value,r_elbow_roll_init_value,
                               r_elbow_yaw_init_value, r_wrist_yaw_init_value]

        # Fill in the Done Episode Criteria list
        self.episode_done_criteria = rospy.get_param("/episode_done_criteria")

        # stablishes connection with simulator
        self.gazebo = GazeboConnection()

        self.controllers_object = ControllersConnection(namespace="pepper_dcm")

        self.pepper_state_object = PepperState(
            min_distance = self.min_distance,
            max_distance = self.max_distance,
            list_of_observations=self.list_of_observations,
            joint_increment_value=self.joint_increment_value,
            joint_limits=self.joint_limits,
            episode_done_criteria=self.episode_done_criteria,
            done_reward=self.done_reward,
            alive_reward=self.alive_reward,
            weight_r1=self.weight_r1,
            weight_r2=self.weight_r2,
            discrete_division=self.discrete_division,
            maximum_base_linear_acceleration=self.maximum_base_linear_acceleration,
            maximum_base_angular_velocity=self.maximum_base_angular_velocity,
            maximum_joint_effort=self.maximum_joint_effort,
        )

        self.pepper_state_object.set_desired_length(self.desired_length.position.x,
                                                          self.desired_length.position.y,
                                                          self.desired_length.position.z)

        self.pepper_joint_pubisher_object = JointPub()
        


        """
        For this version, we consider 10 actions
        1-2) Increment/Decrement RShoulderPitch
        3-4) Increment/Decrement RShoulderRoll
        5-6) Increment/Decrement RElbowRoll
        7-8) Increment/Decrement RElbowYaw
        9-10) Increment/Decrement RWristYaw
        """
        self.action_space = spaces.Discrete(10)
        self.reward_range = (-np.inf, np.inf)

        self._seed()

    # A function to iline 49, in _initialize the random generator
    def _seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]
        
    # Resets the state of the environment and returns an initial observation.
    def _reset(self):

        # 0st: We pause the Simulator
        rospy.logdebug("Pausing SIM...")
        self.gazebo.pauseSim()

        # 1st: resets the simulation to initial values
        rospy.logdebug("Reset SIM...")
        self.gazebo.resetSim()

        # 2nd: We Set the gravity to 0.0 so that we dont fall when reseting joints
        # It also UNPAUSES the simulation
        rospy.logdebug("Remove Gravity...")
        self.gazebo.change_gravity(0.0, 0.0, 0.0)

        # EXTRA: Reset JoinStateControlers because sim reset doesnt reset TFs, generating time problems
        rospy.logdebug("reset_pepper_joint_controllers...")
        self.controllers_object.reset_pepper_joint_controllers()

        # 3rd: resets the robot to initial conditions
        rospy.logdebug("set_init_pose init variable...>>>" + str(self.init_joint_pose))
        # We save that position as the current joint desired position
        init_pos = self.pepper_state_object.init_joints_pose(self.init_joint_pose)

        # 4th: Check all subscribers work.
        # Get the state of the Robot defined by its RPY orientation, distance from
        # desired point, contact force and JointState of the three joints
        rospy.logdebug("check_all_systems_ready...")
        self.pepper_state_object.check_all_systems_ready()

        # 5th: We restore the gravity to original
        rospy.logdebug("Restore Gravity...")
        self.gazebo.change_gravity(0.0, 0.0, -9.81)

        # 6th: pauses simulation
        rospy.logdebug("Pause SIM...")
        self.gazebo.pauseSim()

        # 7th: Get the State Discrete Stringuified version of the observations
        rospy.logdebug("get_observations...")
        observation = self.pepper_state_object.get_observations()
        state = self.get_state(observation)

        return state

    def _step(self, action):

        # Given the action selected by the learning algorithm,
        # we perform the corresponding movement of the robot

        # 1st, decide which action corresponds to which joint is incremented
        next_action_position = self.pepper_state_object.get_action_to_position(action)

        # We move it to that pos
        self.gazebo.unpauseSim()
        self.pepper_joint_pubisher_object.move_joints_jump(next_action_position)
        # Then we send the command to the robot and let it go
        # for running_step seconds
        time.sleep(self.running_step)
        self.gazebo.pauseSim()

        # We now process the latest data saved in the class state to calculate
        # the state and the rewards. This way we guarantee that they work
        # with the same exact data.
        # Generate State based on observations
        observation = self.pepper_state_object.get_observations()

        # finally we get an evaluation based on what happened in the sim
        reward,done = self.pepper_state_object.process_data()

        # Get the State Discrete Stringuified version of the observations
        state = self.get_state(observation)

        return state, reward, done, {}

    def get_state(self, observation):
        """
        We retrieve the Stringuified-Discrete version of the given observation
        :return: state
        """
        return self.pepper_state_object.get_state_as_string(observation)
