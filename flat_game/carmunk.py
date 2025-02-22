import random
import math
import numpy as np

import pygame
from pygame.color import THECOLORS

import pymunk
from pymunk.vec2d import Vec2d
from pymunk.pygame_util import draw

# PyGame init
ncollision = 0
coins = 0
width = 1000
height = 700
pygame.init()
screen = pygame.display.set_mode((width, height))
clock = pygame.time.Clock()

# Turn off alpha since we don't use it.
screen.set_alpha(None)

# Showing sensors and redrawing slows things down.
show_sensors = True
draw_screen = True


class GameState:
    def __init__(self):
        # Global-ish.
        self.crashed = False
        self.is_coin = False
        
        # Physics stuff.
        self.space = pymunk.Space()
        self.space.gravity = pymunk.Vec2d(0., 0.)

        # Create the car.
        self.create_car(100, 100, 0.5)

        # Record steps.
        self.num_steps = 0

        # Create walls.
        static = [
            pymunk.Segment(
                self.space.static_body,
                (0, 1), (0, height), 1),
            pymunk.Segment(
                self.space.static_body,
                (1, height), (width, height), 1),
            pymunk.Segment(
                self.space.static_body,
                (width-1, height), (width-1, 1), 1),
            pymunk.Segment(
                self.space.static_body,
                (1, 1), (width, 1), 1)
        ]
        for s in static:
            s.friction = 1.
            s.group = 1
            s.color = THECOLORS['red']
            s.collision_type = 1
        self.space.add(static)

        # Create some obstacles, semi-randomly.
        # We'll create three and they'll move around to prevent over-fitting.
        self.obstacles = []
        self.obstacles.append(self.create_obstacle(200, 350, 100))
        self.obstacles.append(self.create_obstacle(700, 200, 125))
        self.obstacles.append(self.create_obstacle(600, 600, 35))

        #Create coins at random
        self.coin_pt = []
        for x in range(1,6):
            self.coin_pt.append(self.create_coin_pt(random.randint(1,1000), random.randint(1,600), 60))



    def create_car(self, x, y, r):
        inertia = pymunk.moment_for_circle(1, 0, 14, (0, 0))
        self.car_body = pymunk.Body(1, inertia)
        self.car_body.position = x, y
        self.car_shape = pymunk.Circle(self.car_body, 25)
        self.car_shape.color = THECOLORS["green"]
        self.car_shape.elasticity = 1.0
        self.car_shape.collision_type = 2
        self.car_body.angle = r
        driving_direction = Vec2d(1, 0).rotated(self.car_body.angle)
        self.car_body.apply_impulse(driving_direction)
        self.space.add(self.car_body, self.car_shape)

        
    def create_obstacle(self, x, y, r):
        c_body = pymunk.Body(pymunk.inf, pymunk.inf)
        c_shape = pymunk.Circle(c_body, r)
        c_shape.elasticity = 1.0
        c_body.position = x, y
        c_shape.collision_type = 3
        #c_shape.group = 2
        c_shape.color = THECOLORS["blue"]
        self.space.add(c_body, c_shape)
        return c_body

    def create_coin_pt(self, x, y, r):
        r_body = pymunk.Body(pymunk.inf, pymunk.inf)
        r_shape = pymunk.Circle(r_body, r)
        r_shape.elasticity = 1.0
        r_body.position = x, y
        r_shape.collision_type = 4
        #r_shape.group = 2
        r_shape.color = THECOLORS["orange"]
        self.space.add(r_body, r_shape)
        return r_body

    def frame_step(self, action):
        if action == 0:  # Turn left.
            self.car_body.angle -= .2
            self.car_shape.color = THECOLORS["darkorchid"]
        elif action == 1:  # Turn right.
            self.car_body.angle -= .1
            self.car_shape.color = THECOLORS["darkslateblue"]
        elif action == 2:  # Turn right.
            self.car_body.angle -= .0
            self.car_shape.color = THECOLORS["darkturquoise"]
        elif action == 3:  # Turn right.
            self.car_body.angle += .1
            self.car_shape.color = THECOLORS["darkgreen"]
        elif action == 4:  # Turn right.
            self.car_body.angle += .2
            self.car_shape.color = THECOLORS["orange"]

        
        # Move obstacles.
        if self.num_steps % 100 == 0:
            self.move_obstacles()
            self.move_coin_pt()

        driving_direction = Vec2d(2, 0).rotated(self.car_body.angle)
        self.car_body.velocity = 10 * driving_direction

        # Update the screen and stuff.
        screen.fill(THECOLORS["white"])
        draw(screen, self.space)
        self.space.step(1./10)
        if draw_screen:
            pygame.display.flip()
        clock.tick()

        # Get the current location and the readings there.
        x, y = self.car_body.position
        readings = self.get_sonar_readings(x, y, self.car_body.angle)
        #Even terms in readings are distance and odd terms are color
        normalized_readings = [((i+1)%2)*(x-20.0)/20.0+(i%2)*x for i,x in enumerate(readings)] 
        state = np.array([normalized_readings])

        # Set the reward.
        
        #Give reward and remove coin
        def remove_coin(space, arbiter):
            first_shape = arbiter.shapes[0] 
            space.add_post_step_callback(space.remove, first_shape, first_shape.body)
            self.coin_pt.append(self.create_coin_pt(random.randint(1,900),random.randint(1,600),60))
            self.is_coin = True
            return True
        self.space.add_collision_handler(4, 2, begin = remove_coin)#Uses collision type to handle collision

        def detect_obs(space, arbiter):
            self.crashed = True
            return True
        self.space.add_collision_handler(1, 2, begin = detect_obs, post_solve = detect_obs)#Uses collision type to handle collision
        self.space.add_collision_handler(3, 2, begin = detect_obs, post_solve = detect_obs)

        global ncollision
        global coins
        # Car crashed when any reading == 1
        if self.is_coin:
            reward = 500
            coins = coins + 1
            print("Total collisions: %d Total coins: %d" % (ncollision,coins))
            print(state)
            self.is_coin = False
        elif self.crashed:
            reward = -500
            ncollision = ncollision + 1
            print("Total collisions: %d Total coins: %d" % (ncollision,coins))
            self.recover_from_crash(driving_direction)
        else:
            # Higher readings are better, so return the sum.
            reward = -5 + int(self.sum_readings(readings) / 10)
        self.num_steps += 1

        return reward, state

    def move_obstacles(self):
        # Randomly move obstacles around.
        for obstacle in self.obstacles:
            speed = random.randint(1, 5)
            direction = Vec2d(1, 0).rotated(self.car_body.angle + random.randint(-2, 2))
            obstacle.velocity = speed * direction

    def move_coin_pt(self):
        # Randomly move coins around.
        for coin in self.coin_pt:
            speed = random.randint(1, 5)
            direction = Vec2d(1, 0).rotated(self.car_body.angle + random.randint(-2, 2))
            coin.velocity = speed * direction

            
    def car_is_crashed(self, readings):
        #Thinking of using collision handler instead of this function
        if readings[0] == 1 or readings[2] == 1 or readings[4] == 1 or readings[6] == 1 or readings[8] == 1 and  (readings[1] == 1 or readings[3] == 1 or readings[5] == 1 or readings[7] == 1 or readings[9] == 1):
           #Checks for color
            return True
        else:
            return False

    def recover_from_crash(self, driving_direction):
        """
        We hit something, so recover.
        """
        #while self.crashed:
        # Go backwards.
        self.car_body.velocity = -100 * driving_direction
        self.crashed = False
        for i in range(10):
            self.car_body.angle += .1  # Turn a little.
            screen.fill(THECOLORS["grey7"])  # Red is scary!
            draw(screen, self.space)
            self.space.step(1./10)
            #                if draw_screen:
            #                    pygame.display.flip()
            clock.tick()

    def sum_readings(self, readings):
        """Sum the number of non-zero readings."""
        tot = 0
        for i in readings:
            tot += i
        return tot

    def get_sonar_readings(self, x, y, angle):
        readings = []
        """
        Instead of using a grid of boolean(ish) sensors, sonar readings
        simply return N "distance" readings, one for each sonar
        we're simulating. The distance is a count of the first non-zero
        reading starting at the object. For instance, if the fifth sensor
        in a sonar "arm" is non-zero, then that arm returns a distance of 5.
        """
        # Make our arms.
        arm_left = self.make_sonar_arm(x, y)
        arm_middle = arm_left
        arm_right = arm_left
        arm_rr = arm_left
        arm_ll = arm_left

        # Rotate them and get readings.
        readings.extend(self.get_arm_distance(arm_left, x, y, angle, 0.75, THECOLORS['darkorchid']))
        readings.extend(self.get_arm_distance(arm_ll, x, y, angle, 0.5, THECOLORS['darkslateblue']))
        readings.extend(self.get_arm_distance(arm_middle, x, y, angle, 0, THECOLORS['darkturquoise']))
        readings.extend(self.get_arm_distance(arm_right, x, y, angle, -0.75, THECOLORS['darkgreen']))
        readings.extend(self.get_arm_distance(arm_rr, x, y, angle, -0.5, THECOLORS['orange']))

        if show_sensors:
            pygame.display.update()

        return readings

    def get_arm_distance(self, arm, x, y, angle, offset, color): #Returns distance, color 
        # Used to count the distance.
        i = 0

        # Look at each point and see if we've hit something.
        for point in arm:
            i += 1

            # Move the point to the right spot.
            rotated_p = self.get_rotated_point(
                x, y, point[0], point[1], angle + offset
            )

            # Check if we've hit something. Return the current i (distance)
            # if we did.
            if rotated_p[0] <= 0 or rotated_p[1] <= 0 \
                    or rotated_p[0] >= width or rotated_p[1] >= height:
                return [i,1]  # Sensor is off the screen.  is obstacle color
            else:
                obs = screen.get_at(rotated_p)
                if self.get_track_or_not(obs) != 0:
                    return [i,self.get_track_or_not(obs)] #1 for obstacle color

            if show_sensors:
                pygame.draw.circle(screen, color, (rotated_p), 2)

        # Return the distance for the arm.
        return [i,0]# 0 is track color

    def make_sonar_arm(self, x, y):
        spread = 10  # Default spread.
        distance = 20  # Gap before first sensor.
        arm_points = []
        # Make an arm. We build it flat because we'll rotate it about the
        # center later.
        for i in range(1, 40):
            arm_points.append((distance + x + (spread * i), y))

        return arm_points

    def get_rotated_point(self, x_1, y_1, x_2, y_2, radians):
        # Rotate x_2, y_2 around x_1, y_1 by angle.
        x_change = (x_2 - x_1) * math.cos(radians) + \
            (y_2 - y_1) * math.sin(radians)
        y_change = (y_1 - y_2) * math.cos(radians) - \
            (x_1 - x_2) * math.sin(radians)
        new_x = x_change + x_1
        new_y = height - (y_change + y_1)
        return int(new_x), int(new_y)

    def get_track_or_not(self, reading):
        if reading == THECOLORS['white']:
            return 0
        elif reading == THECOLORS['orange']:
            return -1
        else:
            return 1

if __name__ == "__main__":
    game_state = GameState()
    while True:
        game_state.frame_step((random.randint(0, 5)))
