#!/usr/bin/env python

# Copyright (C) 2017 Maik Heufekes, 05/07/2017.
# License, GNU LGPL, free software, without any warranty.

import sys
import cProfile, pstats
import time 
import rospy
import roslib; roslib.load_manifest("moveit_python")
import sys
import moveit_commander
import moveit_msgs.msg
import baxter_interface
import geometry_msgs.msg
from moveit_python import PlanningSceneInterface, MoveGroupInterface
from geometry_msgs.msg import PoseStamped, PoseArray
from moveit_python.geometry import rotate_pose_msg_by_euler_angles
from math import pi, sqrt
from operator import itemgetter
from std_msgs.msg import String
from copy import deepcopy

# Define initial parameters.
rospy.init_node('pnp', anonymous=True)
# Initialize the move_group API.
moveit_commander.roscpp_initialize(sys.argv)
# Connect the arms to the move group.
both_arms = moveit_commander.MoveGroupCommander('both_arms')
right_arm = moveit_commander.MoveGroupCommander('right_arm')
left_arm = moveit_commander.MoveGroupCommander('left_arm')
# Allow replanning to increase the odds of a solution.
right_arm.allow_replanning(True)
left_arm.allow_replanning(True)
# Set the arms reference frames.
right_arm.set_pose_reference_frame('base')
left_arm.set_pose_reference_frame('base')
# Create baxter_interface limb instance.
leftarm = baxter_interface.limb.Limb('left')
rightarm = baxter_interface.limb.Limb('right')
# Initialize the planning scene interface.
p = PlanningSceneInterface("base")
# Create baxter_interface gripper instance.
leftgripper = baxter_interface.Gripper('left')
rightgripper = baxter_interface.Gripper('right')
leftgripper.calibrate()
rightgripper.calibrate()
leftgripper.open()
rightgripper.open()

def del_meth(somelist, rem):
    # Function to remove objects from the list.
    for i in rem:
        somelist[i]='!' 
    for i in range(0,somelist.count('!')):
        somelist.remove('!')
    return somelist

def picknplace():
    # Define positions.
    pos1 = {'left_e0': -1.69483279891317, 'left_e1':  1.8669726956453, 'left_s0': 0.472137005716569, 'left_s1': -0.38852045702393034, 'left_w0': -1.9770933862776057, 'left_w1': -1.5701993084642143, 'left_w2': -0.6339059781326424, 'right_e0': 1.7238109084167481, 'right_e1': 1.7169079948791506, 'right_s0': 0.36930587426147465, 'right_s1': -0.33249033539428713, 'right_w0': -1.2160632682067871, 'right_w1': 1.668587600115967, 'right_w2': -1.810097327636719}
    lpos1 = {'left_e0': -1.69483279891317, 'left_e1':  1.8669726956453, 'left_s0': 0.472137005716569, 'left_s1': -0.38852045702393034, 'left_w0': -1.9770933862776057, 'left_w1': -1.5701993084642143, 'left_w2': -0.6339059781326424}
    rpos1 = {'right_e0': 1.7238109084167481, 'right_e1': 1.7169079948791506, 'right_s0': 0.36930587426147465, 'right_s1': -0.33249033539428713, 'right_w0': -1.2160632682067871, 'right_w1': 1.668587600115967, 'right_w2': -1.810097327636719}

    placegoal = geometry_msgs.msg.Pose()
    placegoal.position.x = 0.55
    placegoal.position.y = 0.22
    placegoal.position.z = 0
    placegoal.orientation.x = 1.0
    placegoal.orientation.y = 0.0
    placegoal.orientation.z = 0.0
    placegoal.orientation.w = 0.0

    # Define variables.
    offset_zero_point = 0.903
    table_size_x = 0.714655654394
    table_size_y = 1.05043717328
    table_size_z = 0.729766045265
    center_x = 0.457327827197
    center_y = 0.145765166941
    center_z = -0.538116977368
    # The distance from the zero point in Moveit to the ground is 0.903 m.
    # The value is not allways the same. (look in Readme)
    center_z_cube= -offset_zero_point+table_size_z+0.0275/2
    pressure_l_ok=0
    pressure_r_ok=0
    left_ready=0
    right_ready=0
    j=0
    k=0
    start=1
    locs_x_right = []
    locs_x_left = []
    # Initialize a list for the objects and the stacked cubes.
    objlist = ['obj01', 'obj02', 'obj03', 'obj04', 'obj05', 'obj06', 'obj07', 'obj08', 'obj09', 'obj10', 'obj11']
    boxlist= ['box01', 'box02', 'box03', 'box04', 'box05', 'box06', 'box07', 'box08', 'box09', 'box10', 'box11']
    # Clear planning scene.
    p.clear()
    # Add table as attached object.
    p.attachBox('table', table_size_x, table_size_y, table_size_z, center_x, center_y, center_z, 'base', touch_links=['pedestal'])
    p.waitForSync()
    # Move both arms to start state.
    both_arms.set_joint_value_target(pos1)
    both_arms.plan()
    both_arms.go(wait=True)

    # cProfile to measure the performance (time) of the task.
    pr = cProfile.Profile()
    pr.enable()
    # Loop to continue pick and place until all objects are cleared from table.
    while locs_x_right or locs_x_left or start:
        # Only for the start.
	if start:
            start = 0		

        time.sleep(0.5)
        # Receive the data from all objects from the topic "detected_objects_left".
        temp_left = rospy.wait_for_message("detected_objects_left", PoseArray) 
        locs_left = temp_left.poses 
        # Receive the data from all objects from the topic "detected_objects_right".
        temp_right = rospy.wait_for_message("detected_objects_right", PoseArray) 
        locs_right = temp_right.poses 

        locs_x_right = []
        locs_y_right = []
        orien_right = []
        size_right = []

        locs_x_left = []
        locs_y_left = []
        orien_left = []
        size_left = []

        # Adds the data from the objects from the left camera.
        for i in range(len(locs_left)):
            locs_x_left.append(locs_left[i].position.x) 
            locs_y_left.append(locs_left[i].position.y) 
            orien_left.append(locs_left[i].position.z*pi/180)
            size_left.append(locs_left[i].orientation.x)
        # Adds the data from the objects from the right camera.
        for i in range(len(locs_right)):
            locs_x_right.append(locs_right[i].position.x) 
            locs_y_right.append(locs_right[i].position.y) 
            orien_right.append(locs_right[i].position.z*pi/180)
            size_right.append(locs_right[i].orientation.x)

        # Filter objects list to remove multiple detected locations for same objects (left camera).
        ind_rmv = []
        for i in range(0,len(locs_left)):
            if (locs_y_left[i] < 0.28 or locs_y_left[i] > 0.62 or locs_x_left[i] > 0.75):
                ind_rmv.append(i)
                continue
            for j in range(i,len(locs_left)):
                if not (i == j):
                    if sqrt((locs_x_left[i] - locs_x_left[j])**2 + (locs_y_left[i] - locs_y_left[j])**2)<0.018:
                        ind_rmv.append(i)
        
        locs_x_left = del_meth(locs_x_left, ind_rmv)
        locs_y_left = del_meth(locs_y_left, ind_rmv)
        orien_left = del_meth(orien_left, ind_rmv) 
        size_left = del_meth(size_left, ind_rmv)
        # Filter objects list to remove multiple detected locations for same objects (right camera).
        ind_rmv = []
        for i in range(0,len(locs_right)):
            if (locs_y_right[i] > 0.16 or locs_x_right[i] > 0.75):
                ind_rmv.append(i)
                continue
            for j in range(i,len(locs_right)):
                if not (i == j):
                    if sqrt((locs_x_right[i] - locs_x_right[j])**2 + (locs_y_right[i] - locs_y_right[j])**2)<0.018:
                        ind_rmv.append(i)
        
        locs_x_right = del_meth(locs_x_right, ind_rmv)
        locs_y_right = del_meth(locs_y_right, ind_rmv)
        orien_right = del_meth(orien_right, ind_rmv) 
        size_right = del_meth(size_right, ind_rmv)

        # Do the task only if there are still objects on the table.
        if locs_x_right: 
            # Sort objects based on size (largest first to smallest last). This was done to enable stacking large cubes.
	    ig0_right = itemgetter(0)
	    sorted_lists_right = zip(*sorted(zip(size_right,locs_x_right,locs_y_right,orien_right), reverse=True, key=ig0_right))
            locs_x_right = list(sorted_lists_right[1])
            locs_y_right = list(sorted_lists_right[2])
            orien_right = list(sorted_lists_right[3])
	    size_right = list(sorted_lists_right[0])
	    # Initialize the data of the biggest object on the table.
            xn_right = locs_x_right[0]
	    yn_right = locs_y_right[0]	
	    zn_right = -0.16
	    thn_right = orien_right[0]
	    sz_right = size_right[0]
	    if thn_right > pi/4:
		thn_right = -1*(thn_right%(pi/4))

        if locs_x_left: 
            ig0_left = itemgetter(0)
            sorted_lists_left = zip(*sorted(zip(size_left,locs_x_left,locs_y_left,orien_left), reverse=True, key=ig0_left))
	    locs_x_left = list(sorted_lists_left[1])
	    locs_y_left = list(sorted_lists_left[2])
	    orien_left = list(sorted_lists_left[3])
	    size_left = list(sorted_lists_left[0])
	    # Initialize the data of the biggest object on the table.
	    xn_left = locs_x_left[0]
	    yn_left = locs_y_left[0]	
	    zn_left = -0.145
	    thn_left = orien_left[0]
	    sz_left = size_left[0]
	    if thn_left > pi/4:
		thn_left = -1*(thn_left%(pi/4))

        if locs_x_right or locs_x_left:
            # Clear planning scene.
	    p.clear() 
            # Add table as attached object.
            p.attachBox('table', table_size_x, table_size_y, table_size_z, center_x, center_y, center_z, 'base', touch_links=['pedestal'])
	    # Add the detected objects into the planning scene.
	    #for i in range(1,len(locs_x_left)):
	        #p.addBox(objlist[i], 0.05, 0.05, 0.0275, locs_x_left[i], locs_y_left[i], center_z_cube)
	    #for i in range(1,len(locs_x_right)):
	        #p.addBox(objlist[i], 0.05, 0.05, 0.0275, locs_x_right[i], locs_y_right[i], center_z_cube)
	    # Add the stacked objects as collision objects into the planning scene to avoid moving against them.
	    #for e in range(0, k):
	        #p.attachBox(boxlist[e], 0.05, 0.05, 0.0275, placegoal.position.x, placegoal.position.y, center_z_cube+0.0275*(e-1), 'base', touch_links=['cubes'])  
            if k>0:
	        p.attachBox(boxlist[0], 0.07, 0.07, 0.0275*k, placegoal.position.x, placegoal.position.y, center_z_cube, 'base', touch_links=['cubes'])   
	    p.waitForSync()
            if left_ready==0 and locs_x_left:
                # Initialize the approach pickgoal left (5 cm to pickgoal).
                approach_pickgoal_l = geometry_msgs.msg.Pose()
                approach_pickgoal_l.position.x = xn_left
                approach_pickgoal_l.position.y = yn_left
                approach_pickgoal_l.position.z = zn_left+0.05
                approach_pickgoal_l_dummy = PoseStamped() 
                approach_pickgoal_l_dummy.header.frame_id = "base"
                approach_pickgoal_l_dummy.header.stamp = rospy.Time.now()
                approach_pickgoal_l_dummy.pose.position.x = xn_left
                approach_pickgoal_l_dummy.pose.position.y = yn_left
                approach_pickgoal_l_dummy.pose.position.z = zn_left+0.05
                approach_pickgoal_l_dummy.pose.orientation.x = 1.0
                approach_pickgoal_l_dummy.pose.orientation.y = 0.0
                approach_pickgoal_l_dummy.pose.orientation.z = 0.0
                approach_pickgoal_l_dummy.pose.orientation.w = 0.0

	        # Orientate the gripper --> uses function from geometry.py (by Mike Ferguson) to 'rotate a pose' given rpy angles. 
                approach_pickgoal_l_dummy.pose = rotate_pose_msg_by_euler_angles(approach_pickgoal_l_dummy.pose, 0.0, 0.0, thn_left)
                approach_pickgoal_l.orientation.x = approach_pickgoal_l_dummy.pose.orientation.x
                approach_pickgoal_l.orientation.y = approach_pickgoal_l_dummy.pose.orientation.y
                approach_pickgoal_l.orientation.z = approach_pickgoal_l_dummy.pose.orientation.z
                approach_pickgoal_l.orientation.w = approach_pickgoal_l_dummy.pose.orientation.w
                # Move to the approach goal.
                left_arm.set_pose_target(approach_pickgoal_l)
                left_arm.plan()
                left_arm.go(wait=True)
                # Move to the pickgoal.
                pickgoal_l=deepcopy(approach_pickgoal_l)
                pickgoal_l.position.z = zn_left
                left_arm.set_pose_target(pickgoal_l)
                left_arm.plan()
                left_arm.go(wait=True) 
                time.sleep(0.5)
                # Read the force in z direction.
                f_l=leftarm.endpoint_effort()
                z_l= f_l['force']
	        z_force_l= z_l.z
                # Search again for objects, if the gripper isn't at the right position and presses on an object.
	        #print("----->force in z direction:", z_force_l)
	        if z_force_l>-4:
                    leftgripper.close()
                    attempts=0
	            pressure_l_ok=1
                    # If the gripper hadn't enough pressure after 2 seconds it opens and search again for objects.
	            while(leftgripper.force()<25 and pressure_l_ok==1):   
		        time.sleep(0.04)
		        attempts+=1
		        if(attempts>50):
                            leftgripper.open()
                            pressure_l_ok=0
	                    print("----->pressure is to low<-----")
                else:
                    print("----->gripper presses on an object<-----")

                # Move back to the approach pickgoal.
                left_arm.set_pose_target(approach_pickgoal_l)
                left_arm.plan()
                left_arm.go(wait=True) 

	        if pressure_l_ok and z_force_l>-4:
	            left_ready=1
                else:
                    # Move back to lpos1.
                    left_arm.set_joint_value_target(lpos1)
                    left_arm.plan()
                    left_arm.go(wait=True)

            if (left_ready==1 or not locs_x_left) and locs_x_right:
                # Initialize the approach pickgoal right (5 cm to pickgoal).
                approach_pickgoal_r = geometry_msgs.msg.Pose()
                approach_pickgoal_r.position.x = xn_right
                approach_pickgoal_r.position.y = yn_right
                approach_pickgoal_r.position.z = zn_right+0.05
	
                approach_pickgoal_r_dummy = PoseStamped() 
                approach_pickgoal_r_dummy.header.frame_id = "base"
                approach_pickgoal_r_dummy.header.stamp = rospy.Time.now()
                approach_pickgoal_r_dummy.pose.position.x = xn_right
                approach_pickgoal_r_dummy.pose.position.y = yn_right
                approach_pickgoal_r_dummy.pose.position.z = zn_right+0.05
                approach_pickgoal_r_dummy.pose.orientation.x = 1.0
                approach_pickgoal_r_dummy.pose.orientation.y = 0.0
                approach_pickgoal_r_dummy.pose.orientation.z = 0.0
                approach_pickgoal_r_dummy.pose.orientation.w = 0.0

	        # Orientate the gripper --> uses function from geometry.py (by Mike Ferguson) to 'rotate a pose' given rpy angles. 
                approach_pickgoal_r_dummy.pose = rotate_pose_msg_by_euler_angles(approach_pickgoal_r_dummy.pose, 0.0, 0.0, thn_right)
                approach_pickgoal_r.orientation.x = approach_pickgoal_r_dummy.pose.orientation.x
                approach_pickgoal_r.orientation.y = approach_pickgoal_r_dummy.pose.orientation.y
                approach_pickgoal_r.orientation.z = approach_pickgoal_r_dummy.pose.orientation.z
                approach_pickgoal_r.orientation.w = approach_pickgoal_r_dummy.pose.orientation.w
                # Move to the approach goal.
                right_arm.set_pose_target(approach_pickgoal_r)
                right_arm.plan()
                right_arm.go(wait=True) 
                # Move to the pickgoal.
                pickgoal_r=deepcopy(approach_pickgoal_r)
                pickgoal_r.position.z = zn_right
                right_arm.set_pose_target(pickgoal_r)
                right_arm.plan()
                right_arm.go(wait=True) 
                time.sleep(0.5)
                # Read the force in z direction.
                f_r=rightarm.endpoint_effort()
                z_r= f_r['force']
	        z_force_r= z_r.z
                # Search again for objects, if the gripper isn't at the right position and presses on an object.
	        #print("----->force in z direction:", z_force_l)
	        if z_force_r>-4:
                    rightgripper.close()
                    attempts=0
	            pressure_r_ok=1
                    # If the gripper hadn't enough pressure after 2 seconds it opens and search again for objects.
	            while(rightgripper.force()<25 and pressure_r_ok==1):   
		        time.sleep(0.04)
		        attempts+=1
		        if(attempts>50):
                            rightgripper.open()
                            pressure_r_ok=0
	                    print("----->pressure is to low<-----")
                else:
                    print("----->gripper presses on an object<-----")

                # Move back to the approach pickgoal.
                right_arm.set_pose_target(approach_pickgoal_r)
                right_arm.plan()
                right_arm.go(wait=True) 

	        if pressure_r_ok and z_force_r>-4:
                    right_ready=1
                else:
                    # Move back to rpos1.
                    right_arm.set_joint_value_target(rpos1)
                    right_arm.plan()
                    right_arm.go(wait=True)

            if (left_ready==1 or not locs_x_left) and (right_ready==1 or not locs_x_right):  
                # Move both arms to start state.
                #both_arms.set_joint_value_target(pos1)
                #both_arms.plan()
                #both_arms.go(wait=True)
                if(left_ready==1):
                    # Define the approach placegoal for the left arm.
                    # Increase the height of the tower every time by 2.75 cm.
                    approached_placegoal=deepcopy(placegoal)
                    approached_placegoal.position.z = -0.14+(k*0.0275)+0.08
                    # Move to the approach placegoal.
                    left_arm.set_pose_target(approached_placegoal)
                    left_arm.plan()
                    left_arm.go(wait=True)
                    # Define the placegoal.
                    placegoal.position.z = -0.14+(k*0.0275)
                    placegoal.position.x = 0.54
                    left_arm.set_pose_target(placegoal)
                    left_arm.plan()
                    left_arm.go(wait=True) 
	            leftgripper.open()
                    while(leftgripper.force()>10):
		        time.sleep(0.01)
                    k += 1
                    # Move back to the approach placegoal.
                    left_arm.set_pose_target(approached_placegoal)
                    left_arm.plan()
                    left_arm.go(wait=True)
                    # Move back to lpos1.
                    left_arm.set_joint_value_target(lpos1)
                    left_arm.plan()
                    left_arm.go(wait=True)
                    left_ready=0
                if(right_ready==1):
                    # Define the approach placegoal for the right arm.
                    # Increase the height of the tower every time by 2.75 cm.
                    approached_placegoal=deepcopy(placegoal)
                    approached_placegoal.position.z =-0.155+(k*0.0275)+0.08
                    # Move to the approach placegoal.
                    right_arm.set_pose_target(approached_placegoal)
                    right_arm.plan()
                    right_arm.go(wait=True)
                    # Define the placegoal.
                    placegoal.position.z = -0.155+(k*0.0275)
                    placegoal.position.x = 0.53
                    right_arm.set_pose_target(placegoal)
                    right_arm.plan()
                    right_arm.go(wait=True) 
	            rightgripper.open()
                    while(rightgripper.force()>10):
		        time.sleep(0.01)
                    k += 1
                    # Move back to the approach placegoal.
                    right_arm.set_pose_target(approached_placegoal)
                    right_arm.plan()
                    right_arm.go(wait=True)
                    # Move back to rpos1.
                    right_arm.set_joint_value_target(rpos1)
                    right_arm.plan()
                    right_arm.go(wait=True)
                    right_ready=0

    pr.disable()
    sortby = 'cumulative'
    ps=pstats.Stats(pr).sort_stats(sortby).print_stats(0.0)
    p.clear()
    moveit_commander.roscpp_shutdown()
    # Exit MoveIt.
    moveit_commander.os._exit(0)
if __name__=='__main__':
    try:
        rospy.init_node('pnp', anonymous=True)
        picknplace()
    except rospy.ROSInterruptException:
        pass
