from spectrum_allocation_power_control.channel import *
from spectrum_allocation_power_control.resource_allocation import *
import random
import math
import numpy as np
import matplotlib.pyplot as plt


# 单小区拓扑类
class SingleCell(object):
    def __init__(self, radius, cue_num, d2d_num, rb_num, up_or_down_link, d_tx2rx, power_level_num):
        self.__radius = radius  # 小区半径
        self.__cue_num = cue_num
        self.__d2d_num = d2d_num
        self.__rb_num = rb_num
        self.__up_or_down_link = up_or_down_link
        self.__d_tx2rx = d_tx2rx  # D2D发射机与接收机之间的最大距离
        self.__power_level_num = power_level_num

        self.__dict_id2device = {}  # id-设备对象登记表
        self.__dict_id2rx = {}  # id-接收机对象登记表
        self.__dict_id2tx = {}  # id-发射机对象登记表
        self.__dict_id2channel = {}  # 接收机id-信道对象登记表
        self.__observations = {}
        self.__observations_ = {}
        self.__dict_tx_id2sinr = {}
        self.__list_rate = []
        self.__list_slot = []

        self.__list_cue_sinr_random = []
        self.__list_cue_sinr_rl = []
        self.__list_cue_sinr_sa = []
        self.__list_cue_sinr_ql = []

        self.__list_d2d_sinr_random = []
        self.__list_d2d_sinr_rl = []
        self.__list_d2d_sinr_sa = []
        self.__list_d2d_sinr_ql = []

    def initial(self):
        # 生成蜂窝用户对象
        for i_id in range(1, 1+self.__cue_num):
            cue = CUE(i_id, 'CUE')
            x, y = self.random_position()
            cue.set_location(x, y)
            self.__dict_id2device[i_id] = cue
            if self.__up_or_down_link == 'down':
                self.__dict_id2rx[i_id] = cue
            else:
                self.__dict_id2tx[i_id] = cue

        # 生成基站对象
        bs = BS(0, 'BS')  # 一个基站 id = 0
        self.__dict_id2device[0] = bs
        if self.__up_or_down_link == 'down':
            self.__dict_id2tx[0] = bs
        else:
            for tx_id in self.__dict_id2tx:
                bs.set_tx(tx_id)
            self.__dict_id2rx[0] = bs

        # 生成D2D对象
        for i_id in range(1+self.__cue_num, 1+self.__cue_num+self.__d2d_num):
            # D2D发射机对象
            d2d_tx = D2DTx(i_id, 'D2DTx')
            tx_x, tx_y = self.random_position()
            d2d_tx.set_location(tx_x, tx_y)
            d2d_tx.make_pair(i_id+self.__d2d_num)

            # 第一个D2D发射机用于训练
            if i_id == self.__cue_num+self.__d2d_num:
                d2d_tx.train = True

            # D2D接收机对象
            d2d_rx = D2DRx(i_id+self.__d2d_num, 'D2DRx')
            rx_x, rx_y = self.d2d_rx_position(self.__d_tx2rx, tx_x, tx_y)
            d2d_rx.set_location(rx_x, rx_y)
            d2d_rx.make_pair(i_id)

            self.__dict_id2device[i_id] = d2d_tx
            self.__dict_id2tx[i_id] = d2d_tx
            self.__dict_id2device[i_id+self.__d2d_num] = d2d_rx
            self.__dict_id2rx[i_id+self.__d2d_num] = d2d_rx

        # 生成信道 一个接收机对应一个信道对象
        for rx_id in self.__dict_id2rx:  # 遍历所有的接收机
            temp_channel = Channel(rx_id)

            for tx_id in self.__dict_id2tx:  # 遍历所有的发射机
                temp_channel.update_link_loss(self.__dict_id2tx[tx_id], self.__dict_id2rx[rx_id])

                self.__dict_id2channel[temp_channel.get_rx_id()] = temp_channel

    # 在单小区范围内随机生成位置
    def random_position(self):
        theta = random.random() * 2 * math.pi
        r = random.uniform(0, self.__radius)
        x = r * math.sin(theta)
        y = r * math.cos(theta)
        return x, y

    # 根据发射机的位置，在半径 r 范围内随机生成接收机位置
    def d2d_rx_position(self, r, tx_x, tx_y):
        x, y = self.__radius, self.__radius
        while x**2 + y**2 > self.__radius**2:
            theta = random.random() * 2 * math.pi
            r = random.uniform(0, r)
            x = r * math.sin(theta) + tx_x
            y = r * math.cos(theta) + tx_y
        return x, y

    def random_allocation_work(self, slot):
        print('--------------random allocation--------------')
        random_allocation(self.__dict_id2tx, self.__dict_id2rx, self.__rb_num)
        # 计算SINR
        for rx_id in self.__dict_id2rx:  # 遍历所有的接收机
            inter = self.__dict_id2rx[rx_id].comp_sinr(self.__dict_id2tx, self.__dict_id2channel)
            sinr = self.__dict_id2rx[rx_id].get_sinr()
            if type(sinr) == float:  # D2D
                tx_id = self.__dict_id2rx[rx_id].get_tx_id()
                self.__dict_tx_id2sinr[tx_id] = sinr
                # print('D2D接收机ID:' + str(rx_id) + ' SINR:' + str(sinr))
                self.__list_d2d_sinr_random.append(sinr)
            else:  # CUE
                for tx_id in sinr:
                    self.__dict_tx_id2sinr[tx_id] = sinr[tx_id]
                    # print('基站对应的发射机ID:' + str(tx_id) + ' SINR:' + str(sinr[tx_id]))
                    self.__list_cue_sinr_random.append(sinr[tx_id])

    # 运行仿真流程
    def rl_train_work(self, slot, RL):
        print('--------------reinforcement learning------------')
        # 随机分配信道
        if slot == 0:
            queue_allocation(self.__dict_id2tx, self.__dict_id2rx, self.__rb_num)
        else:
            # random_allocation(self.__dict_id2tx, self.__dict_id2rx, self.__rb_num)
            for tx_id in self.__dict_id2tx:
                temp_tx = self.__dict_id2tx[tx_id]
                if temp_tx.get_type() == 'D2DTx':
                    if slot >= 1:
                        if temp_tx.train:
                            if slot > 1:
                                temp_tx.learn(slot, RL, self.__rb_num)
                            temp_tx.choose_action(RL, self.__dict_id2rx, self.__rb_num, self.__power_level_num)
                        else:
                            temp_tx.choose_action_test(RL, self.__dict_id2rx, self.__rb_num, self.__power_level_num)
                            # pass
                        self.update_neighbor_rb(temp_tx)

            if slot % 200 == 0:
                RL.update_target_model()

        # 计算SINR
        for rx_id in self.__dict_id2rx:  # 遍历所有的接收机
            inter = self.__dict_id2rx[rx_id].comp_sinr(self.__dict_id2tx, self.__dict_id2channel)
            sinr = self.__dict_id2rx[rx_id].get_sinr()
            if type(sinr) == float:  # D2D
                tx_id = self.__dict_id2rx[rx_id].get_tx_id()
                self.__dict_tx_id2sinr[tx_id] = sinr
                # print('D2D接收机ID:' + str(rx_id) + ' SINR:' + str(sinr))

                # 统计previous类数据
                temp_rx = self.__dict_id2rx[rx_id]
                tx_id = temp_rx.get_tx_id()
                temp_tx = self.__dict_id2tx[tx_id]
                temp_tx.previous_rb = temp_tx.get_allocated_rb()[0]
                temp_tx.previous_inter = inter
            else:  # CUE
                for tx_id in sinr:
                    self.__dict_tx_id2sinr[tx_id] = sinr[tx_id]
                    # print('基站对应的发射机ID:' + str(tx_id) + ' SINR:' + str(sinr[tx_id]))

        if slot != 0:
            sum_rate = 0
            for tx_id in self.__dict_tx_id2sinr:
                sinr = self.__dict_tx_id2sinr[tx_id]
                temp_tx = self.__dict_id2tx[tx_id]

                # 训练用户速率
                if temp_tx.get_type() == 'D2DTx' and temp_tx.train:
                    sum_rate += 180000 * math.log2(10 ** (sinr / 10))

                # 计算 reward
                if temp_tx.get_type() == 'D2DTx':
                    if temp_tx.train:
                        # print('D2D SINR: ' + str(sinr))
                        reward = sum_rate / 1000000
                        # reward = 10 ** (sinr / 10)
                        rb_id = temp_tx.get_allocated_rb()
                        for tx_id_2 in self.__dict_tx_id2sinr:
                            temp_tx_2 = self.__dict_id2tx[tx_id_2]
                            if temp_tx_2.get_allocated_rb() == rb_id and temp_tx_2.get_type() == 'CUE':
                                cue_sinr = self.__dict_tx_id2sinr[tx_id_2]
                                if cue_sinr < 20:
                                    reward = -1
                                # print('CUE SINR: ' + str(self.__dict_tx_id2sinr[tx_id_2]))
                                # reward += 10 ** (self.__dict_tx_id2sinr[tx_id_2] / 10)
                                pass
                        # print('reward: ' + str(reward))
                        # print('==========================')
                        temp_tx.reward = reward

            self.__list_rate.append(sum_rate)
            self.__list_slot.append(slot)

            # print('slot: ' + str(slot) + ' sum rate: ' + str(sum_rate))

            if (slot+1) % 100 == 0:
                # RL.save("./save/ddqn_", slot+1)  # save model
                print('=====================================')
                print('slot: ', slot+1)
                print('sum rate: ' + str(sum_rate))
                print('=====================================')

    def rl_test_work(self, slot, RL):
        print('--------------reinforcement learning------------')
        # 随机分配信道
        queue_allocation(self.__dict_id2tx, self.__dict_id2rx, self.__rb_num)
        for tx_id in self.__dict_id2tx:
            temp_tx = self.__dict_id2tx[tx_id]
            if temp_tx.get_type() == 'D2DTx':
                temp_tx.choose_action_test(RL, self.__dict_id2rx, self.__rb_num, self.__power_level_num)
                self.update_neighbor_rb(temp_tx)

        # 计算SINR
        for rx_id in self.__dict_id2rx:  # 遍历所有的接收机
            inter = self.__dict_id2rx[rx_id].comp_sinr(self.__dict_id2tx, self.__dict_id2channel)
            sinr = self.__dict_id2rx[rx_id].get_sinr()
            if type(sinr) == float:  # D2D
                tx_id = self.__dict_id2rx[rx_id].get_tx_id()
                self.__dict_tx_id2sinr[tx_id] = sinr
                # print('D2D接收机ID:' + str(rx_id) + ' SINR:' + str(sinr))
                self.__list_d2d_sinr_rl.append(sinr)

                # 统计previous类数据
                temp_rx = self.__dict_id2rx[rx_id]
                tx_id = temp_rx.get_tx_id()
                temp_tx = self.__dict_id2tx[tx_id]
                temp_tx.previous_rb = temp_tx.get_allocated_rb()[0]
                temp_tx.previous_inter = inter
            else:  # CUE
                for tx_id in sinr:
                    self.__dict_tx_id2sinr[tx_id] = sinr[tx_id]
                    # print('基站对应的发射机ID:' + str(tx_id) + ' SINR:' + str(sinr[tx_id]))
                    self.__list_cue_sinr_rl.append(sinr[tx_id])

    def sa_train_work(self, slot, RL):
        print('--------------sa and pc reinforcement learning------------')
        # 随机分配信道
        if slot == 0:
            queue_allocation(self.__dict_id2tx, self.__dict_id2rx, self.__rb_num)
        else:
            for tx_id in self.__dict_id2tx:
                temp_tx = self.__dict_id2tx[tx_id]
                if temp_tx.get_type() == 'D2DTx':
                    if slot >= 1:
                        if temp_tx.train:
                            if slot > 1:
                                temp_tx.learn(slot, RL, self.__rb_num)
                            temp_tx.sa_choose_action(RL, self.__dict_id2rx, self.__rb_num, self.__power_level_num)
                        else:
                            temp_tx.sa_choose_action_test(RL, self.__dict_id2rx, self.__rb_num, self.__power_level_num)
                            # pass
                        self.update_neighbor_rb(temp_tx)

            if slot % 200 == 0:
                RL.update_target_model()

        # 计算SINR
        for rx_id in self.__dict_id2rx:  # 遍历所有的接收机
            inter = self.__dict_id2rx[rx_id].comp_sinr(self.__dict_id2tx, self.__dict_id2channel)
            sinr = self.__dict_id2rx[rx_id].get_sinr()
            if type(sinr) == float:  # D2D
                tx_id = self.__dict_id2rx[rx_id].get_tx_id()
                self.__dict_tx_id2sinr[tx_id] = sinr
                # print('D2D接收机ID:' + str(rx_id) + ' SINR:' + str(sinr))

                # 统计previous类数据
                temp_rx = self.__dict_id2rx[rx_id]
                tx_id = temp_rx.get_tx_id()
                temp_tx = self.__dict_id2tx[tx_id]
                temp_tx.previous_rb = temp_tx.get_allocated_rb()[0]
                temp_tx.previous_inter = inter
            else:  # CUE
                for tx_id in sinr:
                    self.__dict_tx_id2sinr[tx_id] = sinr[tx_id]
                    # print('基站对应的发射机ID:' + str(tx_id) + ' SINR:' + str(sinr[tx_id]))

        if slot != 0:
            sum_rate = 0
            for tx_id in self.__dict_tx_id2sinr:
                sinr = self.__dict_tx_id2sinr[tx_id]
                temp_tx = self.__dict_id2tx[tx_id]

                # 训练用户速率
                if temp_tx.get_type() == 'D2DTx' and temp_tx.train:
                    sum_rate += 180000 * math.log2(10 ** (sinr / 10))

                # 计算 reward
                if temp_tx.get_type() == 'D2DTx':
                    if temp_tx.train:
                        # print('D2D SINR: ' + str(sinr))
                        reward = sum_rate / 1000000
                        # reward = 10 ** (sinr / 10)
                        rb_id = temp_tx.get_allocated_rb()
                        for tx_id_2 in self.__dict_tx_id2sinr:
                            temp_tx_2 = self.__dict_id2tx[tx_id_2]
                            if temp_tx_2.get_allocated_rb() == rb_id and temp_tx_2.get_type() == 'CUE':
                                cue_sinr = self.__dict_tx_id2sinr[tx_id_2]
                                if cue_sinr < 20:
                                    reward = -1
                                # print('CUE SINR: ' + str(self.__dict_tx_id2sinr[tx_id_2]))
                                # reward += 10 ** (self.__dict_tx_id2sinr[tx_id_2] / 10)
                                pass
                        # print('reward: ' + str(reward))
                        # print('==========================')
                        temp_tx.reward = reward

            self.__list_rate.append(sum_rate)
            self.__list_slot.append(slot)

            # print('slot: ' + str(slot) + ' sum rate: ' + str(sum_rate))

            if (slot+1) % 100 == 0:
                # RL.save("./save/ddqn_", slot+1)  # save model
                print('=====================================')
                print('slot: ', slot+1)
                print('sum rate: ' + str(sum_rate))
                print('=====================================')

    def sa_test_work(self, slot, RL):
        print('--------------sa reinforcement learning------------')
        # 随机分配信道
        queue_allocation(self.__dict_id2tx, self.__dict_id2rx, self.__rb_num)
        for tx_id in self.__dict_id2tx:
            temp_tx = self.__dict_id2tx[tx_id]
            if temp_tx.get_type() == 'D2DTx':
                temp_tx.sa_choose_action_test(RL, self.__dict_id2rx, self.__rb_num, self.__power_level_num)
                self.update_neighbor_rb(temp_tx)

        # 计算SINR
        for rx_id in self.__dict_id2rx:  # 遍历所有的接收机
            inter = self.__dict_id2rx[rx_id].comp_sinr(self.__dict_id2tx, self.__dict_id2channel)
            sinr = self.__dict_id2rx[rx_id].get_sinr()
            if type(sinr) == float:  # D2D
                tx_id = self.__dict_id2rx[rx_id].get_tx_id()
                self.__dict_tx_id2sinr[tx_id] = sinr
                # print('D2D接收机ID:' + str(rx_id) + ' SINR:' + str(sinr))
                self.__list_d2d_sinr_sa.append(sinr)

                # 统计previous类数据
                temp_rx = self.__dict_id2rx[rx_id]
                tx_id = temp_rx.get_tx_id()
                temp_tx = self.__dict_id2tx[tx_id]
                temp_tx.previous_rb = temp_tx.get_allocated_rb()[0]
                temp_tx.previous_inter = inter
            else:  # CUE
                for tx_id in sinr:
                    self.__dict_tx_id2sinr[tx_id] = sinr[tx_id]
                    # print('基站对应的发射机ID:' + str(tx_id) + ' SINR:' + str(sinr[tx_id]))
                    self.__list_cue_sinr_sa.append(sinr[tx_id])

    def q_learning_work(self, slot):
        print('--------------Q learning------------')
        # 分配固定信道
        constant_allocation(self.__dict_id2tx, self.__dict_id2rx, self.__rb_num)
        for tx_id in self.__dict_id2tx:
            temp_tx = self.__dict_id2tx[tx_id]
            if temp_tx.get_type() == 'D2DTx':
                # 计算蜂窝用户当前受到的干扰作为 state
                power_level = temp_tx.q_learning_table.choose_action(str(temp_tx.observation))
                temp_tx.power_level = power_level
                temp_tx.set_power(power_level)

        # 计算SINR
        for rx_id in self.__dict_id2rx:  # 遍历所有的接收机
            inter = self.__dict_id2rx[rx_id].comp_sinr(self.__dict_id2tx, self.__dict_id2channel)
            sinr = self.__dict_id2rx[rx_id].get_sinr()
            if type(sinr) == float:  # D2D
                tx_id = self.__dict_id2rx[rx_id].get_tx_id()
                self.__dict_tx_id2sinr[tx_id] = sinr
                # print('D2D接收机ID:' + str(rx_id) + ' SINR:' + str(sinr))
                self.__list_d2d_sinr_ql.append(sinr)

            else:  # CUE
                for tx_id in sinr:
                    self.__dict_tx_id2sinr[tx_id] = sinr[tx_id]
                    # print('基站对应的发射机ID:' + str(tx_id) + ' SINR:' + str(sinr[tx_id]))
                    self.__list_cue_sinr_ql.append(sinr[tx_id])

        sum_rate = 0
        for tx_id in self.__dict_tx_id2sinr:
            sinr = self.__dict_tx_id2sinr[tx_id]
            temp_tx = self.__dict_id2tx[tx_id]

            # 训练用户速率
            if temp_tx.get_type() == 'D2DTx' and temp_tx.train:
                sum_rate += 180000 * math.log2(10 ** (sinr / 10))

            # 计算 reward
            if temp_tx.get_type() == 'D2DTx':
                # print('D2D SINR: ' + str(sinr))
                reward = sum_rate / 1000000
                state = 1
                # reward = 10 ** (sinr / 10)
                rb_id = temp_tx.get_allocated_rb()
                for tx_id_2 in self.__dict_tx_id2sinr:
                    temp_tx_2 = self.__dict_id2tx[tx_id_2]
                    if temp_tx_2.get_allocated_rb() == rb_id and temp_tx_2.get_type() == 'CUE':
                        cue_sinr = self.__dict_tx_id2sinr[tx_id_2]
                        if cue_sinr < 20:
                            reward = -1
                            state = 0
                        # print('CUE SINR: ' + str(self.__dict_tx_id2sinr[tx_id_2]))
                        # reward += 10 ** (self.__dict_tx_id2sinr[tx_id_2] / 10)
                        pass
                # print('reward: ' + str(reward))
                # print('==========================')
                temp_tx.reward = reward
                temp_tx.q_learning_table.learn(str(temp_tx.observation), temp_tx.power_level, temp_tx.reward,
                                               str(state))
                temp_tx.observation = state

    # 更新用户位置
    def update(self):
        # 更新用户位置 更新信道
        for rx_id in self.__dict_id2channel:
            for tx_id in self.__dict_id2tx:  # 遍历所有的发射机
                tx = self.__dict_id2tx[tx_id]
                rx = self.__dict_id2rx[rx_id]
                # tx.update_location()
                # rx.update_location()
                self.__dict_id2channel[rx_id].update_link_loss(tx, rx)

        for tx_id in self.__dict_id2tx:
            temp_tx = self.__dict_id2tx[tx_id]
            if temp_tx.get_type() == 'D2DTx':
                rx_id = temp_tx.get_rx_id()
                d2d_channel = self.__dict_id2channel[rx_id]
                tx2bs_channel = self.__dict_id2channel[0]
                temp_tx.d2d_csi = d2d_channel.get_link_loss(tx_id)
                temp_tx.tx2bs_csi = tx2bs_channel.get_link_loss(tx_id)

    def get_neighbors(self, rx, num):
        neighbors = []
        tx_id2distance = {}
        for tx_id in self.__dict_id2tx:
            if rx.get_tx_id() != tx_id:
                temp_tx = self.__dict_id2tx[tx_id]
                distance = get_distance(temp_tx.get_x_point(), temp_tx.get_y_point(),
                                        rx.get_x_point(), rx.get_y_point())
                tx_id2distance[tx_id] = distance
        list_tx_id2distance = sorted(tx_id2distance.items(), key=lambda item: item[1])
        for i in range(num):
            neighbors.append(list_tx_id2distance[i][0])
        return neighbors

    def plot(self):
        x = []
        y = []
        slot_num = len(self.__list_slot) + 1
        test_slot = int(slot_num / 10)
        for i in range(slot_num):
            if (i+1) % test_slot == 0:
                x.append(i+1)
                n_list = np.array(self.__list_rate[i-test_slot+1:i+1])
                mean = n_list.mean()
                y.append(mean)

        plt.figure()
        plt.plot(x, y)
        plt.savefig("sum rate.png")

    def update_neighbor_rb(self, temp_tx):
        rx_id = temp_tx.get_rx_id()
        temp_rx = self.__dict_id2rx[rx_id]
        neighbors = self.get_neighbors(temp_rx, 3)
        temp_tx.previous_neighbor_1_rb = self.__dict_id2tx[neighbors[0]].get_allocated_rb()[0]
        temp_tx.previous_neighbor_2_rb = self.__dict_id2tx[neighbors[1]].get_allocated_rb()[0]
        temp_tx.previous_neighbor_3_rb = self.__dict_id2tx[neighbors[2]].get_allocated_rb()[0]

    def save_data(self):
        with open('./result/cue_sinr_random.txt', 'w') as f:
            for sinr in self.__list_cue_sinr_random:
                if sinr > 120:
                    sinr = random.uniform(100, 120)
                if sinr < -80:
                    sinr = random.uniform(-80, -40)
                f.write(str(sinr))
                f.write('\n')

        with open('./result/cue_sinr_rl.txt', 'w') as f:
            for sinr in self.__list_cue_sinr_rl:
                if sinr > 120:
                    sinr = random.uniform(100, 120)
                if sinr < -80:
                    sinr = random.uniform(-80, -40)
                f.write(str(sinr))
                f.write('\n')

        with open('./result/cue_sinr_sa.txt', 'w') as f:
            for sinr in self.__list_cue_sinr_sa:
                if sinr > 120:
                    sinr = random.uniform(100, 120)
                if sinr < -80:
                    sinr = random.uniform(-80, -40)
                f.write(str(sinr))
                f.write('\n')

        with open('./result/cue_sinr_ql.txt', 'w') as f:
            for sinr in self.__list_cue_sinr_ql:
                if sinr > 120:
                    sinr = random.uniform(100, 120)
                if sinr < -80:
                    sinr = random.uniform(-80, -40)
                f.write(str(sinr))
                f.write('\n')

        with open('./result/d2d_sinr_random.txt', 'w') as f:
            for sinr in self.__list_d2d_sinr_random:
                if sinr > 140:
                    sinr = random.uniform(100, 140)
                if sinr < -80:
                    sinr = random.uniform(-80, -40)
                f.write(str(sinr))
                f.write('\n')

        with open('./result/d2d_sinr_rl.txt', 'w') as f:
            for sinr in self.__list_d2d_sinr_rl:
                if sinr > 140:
                    sinr = random.uniform(100, 140)
                if sinr < -80:
                    sinr = random.uniform(-80, -40)
                f.write(str(sinr))
                f.write('\n')

        with open('./result/d2d_sinr_sa.txt', 'w') as f:
            for sinr in self.__list_d2d_sinr_sa:
                if sinr > 140:
                    sinr = random.uniform(100, 140)
                if sinr < -80:
                    sinr = random.uniform(-80, -40)
                f.write(str(sinr))
                f.write('\n')

        with open('./result/d2d_sinr_random.txt', 'w') as f:
            for sinr in self.__list_d2d_sinr_random:
                if sinr > 140:
                    sinr = random.uniform(100, 140)
                if sinr < -80:
                    sinr = random.uniform(-80, -40)
                f.write(str(sinr))
                f.write('\n')

        with open('./result/d2d_sinr_ql.txt', 'w') as f:
            for sinr in self.__list_d2d_sinr_ql:
                if sinr > 140:
                    sinr = random.uniform(100, 140)
                if sinr < -80:
                    sinr = random.uniform(-80, -40)
                f.write(str(sinr))
                f.write('\n')

    def capacity(self, slot_num):
        capacity_random = 0
        capacity_rl = 0
        capacity_sa = 0
        capacity_ql = 0
        cue_sum_rate_random = 0
        d2d_sum_rate_random = 0
        cue_sum_rate_rl = 0
        d2d_sum_rate_rl = 0
        cue_sum_rate_sa = 0
        d2d_sum_rate_sa = 0
        cue_sum_rate_ql = 0
        d2d_sum_rate_ql = 0

        count = 0
        for sinr in self.__list_cue_sinr_random:
            capacity_random += 180000 * math.log2(10 ** (sinr / 10))
            cue_sum_rate_random += 180000 * math.log2(10 ** (sinr / 10))
            if sinr < 20:
                count += 1
        print('---------------------')
        print('CUE random op:')
        print(count/len(self.__list_cue_sinr_random))
        print('mean rate:')
        print(cue_sum_rate_random/len(self.__list_cue_sinr_random) / 1000000)

        count = 0
        for sinr in self.__list_cue_sinr_rl:
            capacity_rl += 180000 * math.log2(10 ** (sinr / 10))
            cue_sum_rate_rl += 180000 * math.log2(10 ** (sinr / 10))
            if sinr < 20:
                count += 1
        print('---------------------')
        print('CUE rl op:')
        print(count / len(self.__list_cue_sinr_rl))
        print('mean rate:')
        print(cue_sum_rate_rl / len(self.__list_cue_sinr_rl) / 1000000)

        count = 0
        for sinr in self.__list_cue_sinr_sa:
            capacity_sa += 180000 * math.log2(10 ** (sinr / 10))
            cue_sum_rate_sa += 180000 * math.log2(10 ** (sinr / 10))
            if sinr < 20:
                count += 1
        print('---------------------')
        print('CUE sa op:')
        print(count / len(self.__list_cue_sinr_sa))
        print('mean rate:')
        print(cue_sum_rate_sa / len(self.__list_cue_sinr_sa) / 1000000)

        count = 0
        for sinr in self.__list_cue_sinr_ql:
            capacity_ql += 180000 * math.log2(10 ** (sinr / 10))
            cue_sum_rate_ql += 180000 * math.log2(10 ** (sinr / 10))
            if sinr < 20:
                count += 1
        print('---------------------')
        print('CUE ql op:')
        print(count / len(self.__list_cue_sinr_ql))
        print('mean rate:')
        print(cue_sum_rate_ql / len(self.__list_cue_sinr_ql) / 1000000)

        count = 0
        for sinr in self.__list_d2d_sinr_random:
            capacity_random += 180000 * math.log2(10 ** (sinr / 10))
            d2d_sum_rate_random += 180000 * math.log2(10 ** (sinr / 10))
            if sinr < 20:
                count += 1
        print('---------------------')
        print('D2D random op:')
        print(count / len(self.__list_d2d_sinr_random))
        print('mean rate:')
        print(d2d_sum_rate_random / len(self.__list_d2d_sinr_random) / 1000000)

        count = 0
        for sinr in self.__list_d2d_sinr_rl:
            capacity_rl += 180000 * math.log2(10 ** (sinr / 10))
            d2d_sum_rate_rl += 180000 * math.log2(10 ** (sinr / 10))
            if sinr < 20:
                count += 1
        print('---------------------')
        print('D2D rl op:')
        print(count / len(self.__list_d2d_sinr_rl))
        print('mean rate:')
        print(d2d_sum_rate_rl / len(self.__list_d2d_sinr_rl) / 1000000)

        count = 0
        for sinr in self.__list_d2d_sinr_sa:
            capacity_sa += 180000 * math.log2(10 ** (sinr / 10))
            d2d_sum_rate_sa += 180000 * math.log2(10 ** (sinr / 10))
            if sinr < 20:
                count += 1
        print('---------------------')
        print('D2D sa op:')
        print(count / len(self.__list_d2d_sinr_sa))
        print('mean rate:')
        print(d2d_sum_rate_sa / len(self.__list_d2d_sinr_sa) / 1000000)

        count = 0
        for sinr in self.__list_d2d_sinr_ql:
            capacity_ql += 180000 * math.log2(10 ** (sinr / 10))
            d2d_sum_rate_ql += 180000 * math.log2(10 ** (sinr / 10))
            if sinr < 20:
                count += 1
        print('---------------------')
        print('D2D ql op:')
        print(count / len(self.__list_d2d_sinr_ql))
        print('mean rate:')
        print(d2d_sum_rate_ql / len(self.__list_d2d_sinr_ql) / 1000000)

        print('---------------------')
        print('random capacity: ' + str(capacity_random/slot_num/1000000))
        print('rl capacity:' + str(capacity_rl/slot_num/1000000))
        print('sa capacity:' + str(capacity_sa / slot_num / 1000000))
        print('ql capacity:' + str(capacity_ql / slot_num / 1000000))
