# author: Zhiliang Zhou
# E-Mail: zhouzhiliang@gmail.com
# n-bar linkage robot arm env
# learned from 2-bar linkage example, https://github.com/MorvanZhou/train-robot-arm-from-scratch

import numpy as np
import pyglet


def cbox_to_bbox(cbox):
    """
    convert center box definition to bounding box definition
    :param cbox: (x_center, y_center, width, height
    :return: bbox: (x_topleft, y_topleft, x_bottomright, y_bottomright)
    """
    bbox = np.zeros(4)
    bbox[0] = cbox[0] - cbox[2] / 2
    bbox[1] = cbox[1] - cbox[3] / 2
    bbox[2] = cbox[0] + cbox[2] / 2
    bbox[3] = cbox[1] + cbox[3] / 2
    return bbox


def bbox_to_cbox(bbox):
    cbox = np.zeros(4)
    cbox[0] = (bbox[0] + bbox[2]) / 2
    cbox[1] = (bbox[1] + bbox[3]) / 2
    cbox[2] = bbox[2] - bbox[0]
    cbox[3] = bbox[3] - bbox[1]
    return cbox


class Viewer(pyglet.window.Window):

    def __init__(self,
                 goal_bbox,
                 n_bars=2,
                 bar_width=10,
                 canvas_width=400,
                 canvas_height=400,
                 arm_center_x=200,
                 arm_center_y=200):
        super(Viewer, self).__init__(width=canvas_width, height=canvas_height, resizable=False, caption='Arm', vsync=False)
        # window background color
        pyglet.gl.glClearColor(1, 1, 1, 1)

        self.bar_width = bar_width
        self.n_bars = n_bars
        self.origin = np.array([arm_center_x, arm_center_y])
        self.bar_position = np.zeros([n_bars, 4])

        # display whole batch at once
        self.batch = pyglet.graphics.Batch()
        # add target box
        self.goal = self.batch.add(
            4, pyglet.gl.GL_QUADS, None,    # 4 corners
            ('v2f', [goal_bbox[0], goal_bbox[1],
                     goal_bbox[0], goal_bbox[3],
                     goal_bbox[2], goal_bbox[3],
                     goal_bbox[2], goal_bbox[1]]),
            ('c3B', (86, 109, 249) * 4))    # color

        # add bars
        self.bars = []
        for i in range(n_bars):
            self.bars.append(self.batch.add(4, pyglet.gl.GL_QUADS, None,    # 4 corners
                                            ('v2f', [250, 250,              # x1, y1
                                                     250, 300,              # x2, y2
                                                     260, 300,              # x3, y3
                                                     260, 250]),            # x4, y4
                                            ('c3B', (249, 86, 86) * 4,)))    # color

    def on_draw(self):
        self.clear()
        self.batch.draw()

    def update(self, arm_info, goal_bbox):
        """
        :param bar_state: (x1,y1,x2,y2,r,theta)
        :return:
        """
        # update bars
        x1, y1, x2, y2 = 0, 0, 0, 0
        for i in range(arm_info.shape[0]):
            theta = arm_info[i][0]
            length = arm_info[i][1]
            if i == 0:
                x1 = self.origin[0]
                y1 = self.origin[1]

                x2 = x1 + length * np.cos(theta)
                y2 = y1 + length * np.sin(theta)
            else:
                x1 = x2  # next bar's start is previous bars's end
                y1 = y2

                x2 = x1 + length * np.cos(theta)
                y2 = y1 + length * np.sin(theta)

            # draw rectangle based on line
            p1x = x1 + 0.5 * self.bar_width * np.cos(np.pi * 0.5 - theta)
            p1y = y1 - 0.5 * self.bar_width * np.sin(np.pi * 0.5 - theta)

            p2x = x1 - 0.5 * self.bar_width * np.cos(np.pi * 0.5 - theta)
            p2y = y1 + 0.5 * self.bar_width * np.sin(np.pi * 0.5 - theta)

            p4x = x2 + 0.5 * self.bar_width * np.cos(np.pi * 0.5 - theta)
            p4y = y2 - 0.5 * self.bar_width * np.sin(np.pi * 0.5 - theta)

            p3x = x2 - 0.5 * self.bar_width * np.cos(np.pi * 0.5 - theta)
            p3y = y2 + 0.5 * self.bar_width * np.sin(np.pi * 0.5 - theta)
            self.bars[i].vertices = [p1x, p1y, p2x, p2y, p3x, p3y, p4x, p4y]

        # update goal
        self.goal.vertices = [goal_bbox[0], goal_bbox[1],
                              goal_bbox[0], goal_bbox[3],
                              goal_bbox[2], goal_bbox[3],
                              goal_bbox[2], goal_bbox[1]]

        # render
        self.switch_to()
        self.dispatch_events()
        self.dispatch_event('on_draw')
        self.flip()


class ArmEnv(object):
    def __init__(self,
                 n_bar=2,
                 goal=None,
                 bar_length = 100,
                 canvas_width=400,
                 canvas_height=400):

        self.action_size = n_bar
        self.state_size = n_bar * 2 + n_bar * 2 + 1  # n_bar * [x,y],  n_bar*[distance], done_flag
        self.n_bar = n_bar
        self.viewer = None
        self.dt = .1  # refresh rate
        self.action_bound = [-1, 1]

        self.arm_info = np.zeros([n_bar, 2])
        self.arm_info[:, 0] = np.pi / 6  # angles information
        self.arm_info[:, 1] = bar_length        # bar length
        self.on_goal = 0

        # cartesian coordinates buffer for internal usage
        self.bar_coordinates = np.zeros([n_bar, 4])  # x1,y1,x2,y2

        # canvas setup
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.origin = np.array([canvas_width / 2.0, canvas_height / 2.0])  # x,y the parent rotation center of first bar

        if goal is None:
            self.goal_cbox = np.array([100, 100, 40, 40], dtype=np.float)  # blue box bbox=(x,y,w,h)
        else:
            self.goal_cbox = goal
        self.goal_bbox = cbox_to_bbox(self.goal_cbox)

    def step(self, action):
        done = False
        action = np.clip(action, *self.action_bound)
        self.arm_info[:, 0] += action * self.dt
        self.arm_info[:, 0] %= np.pi * 2    # normalize
        # polar to cartesian
        self.update_arm_coordinates()

        # sensing feature
        dist = self.get_distance()
        # reward = -np.sqrt(dist2[0]**2+dist2[1]**2)
        reward = -np.linalg.norm(dist[-1])

        done_x = self.goal_bbox[0] < self.bar_coordinates[-1][2] < self.goal_bbox[2]
        done_y = self.goal_bbox[1] < self.bar_coordinates[-1][3] < self.goal_bbox[3]
        if done_x and done_y:
            reward += 1.
            self.on_goal += 1
            if self.on_goal >= 50:
                done = True
        else:
            self.on_goal = 0
        # state
        s = np.concatenate((self.bar_coordinates[:, -2:].flatten()/400,
                            dist.flatten(),
                            [1. if self.on_goal else 0.]))
        return s, reward, done, {}

    def reset(self):
        self.goal_cbox = np.array([np.random.rand()*400,
                                   np.random.rand()*400,
                                   40, 40], dtype=np.float)  # blue box bbox=(x,y,w,h)
        self.goal_bbox = cbox_to_bbox(self.goal_cbox)
        self.arm_info[:, 0] = 2 * np.pi * np.random.rand(2)
        # polar to cartesian
        self.update_arm_coordinates()

        self.on_goal = 0

        # sensing feature
        dist = self.get_distance()

        # state
        s = np.concatenate((self.bar_coordinates[:, -2:].flatten() / 400,
                            dist.flatten(),
                            [1. if self.on_goal else 0.]))
        return s

    def render(self):
        if self.viewer is None:
            self.viewer = Viewer(self.goal_bbox, n_bars=2)
        self.viewer.update(self.arm_info, self.goal_bbox)

    def sample_rand_action(self):
        return np.random.rand(2)-0.5    # two radians

    def update_arm_coordinates(self):
        """
        need to update bars one by one, due to dependencies. can not update matrix in one step
        :return:
        """
        for i in range(self.n_bar):
            # update start point of bar first
            if i == 0:
                self.bar_coordinates[i][:2] = self.origin
            else:
                self.bar_coordinates[i][:2] = self.bar_coordinates[i - 1][2:2 + 2]  # next bar's start is previous bars's end
            # update end point with
            theta = self.arm_info[i][0]
            length = self.arm_info[i][1]
            self.bar_coordinates[i][2] = self.bar_coordinates[i][0] + length * np.cos(theta)  # x = x_start + length * cos(theta)
            self.bar_coordinates[i][3] = self.bar_coordinates[i][1] + length * np.sin(theta)  # y = y_start + length * sin(theta)

    def get_distance(self):
        # sensing information
        # distance between end-point of bar and goal

        dist = (self.goal_bbox[:2] - self.bar_coordinates[:, 2:2+2]) / 400

        # dist1 = [(self.goal_cbox[0] - self.bar_coordinates[0][2]) / 400,
        #          (self.goal_cbox[1] - self.bar_coordinates[0][3]) / 400]
        # dist2 = [(self.goal_cbox[0] - self.bar_coordinates[1][2]) / 400,
        #          (self.goal_cbox[1] - self.bar_coordinates[1][3]) / 400]

        return dist


if __name__ == '__main__':
    env = ArmEnv()
    while True:
        env.render()
        state, reward, done, info = env.step(env.sample_rand_action())
        if done is True:
            break
