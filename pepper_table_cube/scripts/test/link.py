#!/usr/bin/env python

from gazebo_msgs.msg import LinkStates
from geometry_msgs.msg import Pose, Quaternion, Twist, Vector3
import rospy
import time

class Link():
  def __init__(self, name):
    self.name = name
    self.topic = '/gazebo/link_states'

    msg = rospy.wait_for_message(self.topic, LinkStates)
    self.index = msg.name.index(self.name)
    # rospy.Subscriber("/gazebo/link_states", LinkStates, self.links_state_callback)
    # rospy.spin()
  
  def links_state_callback(self, msg):
    self.links_state = msg
    self.index = self.links_state.name.index(self.name)

  def get_position(self):
    msg = rospy.wait_for_message(self.topic, LinkStates)
    return msg.pose[self.index].position
  
  def get_twist(self, msg):
    msg = rospy.wait_for_message(self.topic, LinkStates)
    return msg.twist[self.index]

if __name__ == '__main__':   
  try:
    rospy.init_node('link_state_sub', anonymous=True)
    r_gripper = Link("pepper::r_gripper")
    print(r_gripper.get_position())
  except rospy.ROSInterruptException: pass
  