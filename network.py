# coding=utf-8
import keras
from keras import Input, Model
from keras.applications.vgg16 import VGG16
from keras.layers import Concatenate, Conv2D, UpSampling2D, BatchNormalization
import argparse

parser = argparse.ArgumentParser(description='options')
parser.add_argument('--section', type=str, default='local',
                    help='cfg to load')
args = parser.parse_args()

if args.section == 'local':
    import cfg_local as cfg
if args.section == 'server':
    import cfg_server as cfg

"""
input_shape=(img.height, img.width, 3), height and width must scaled by 32.
So images's height and width need to be pre-processed to the nearest num that
scaled by 32.And the annotations xy need to be scaled by the same ratio 
as height and width respectively.
"""

class East:

    def __init__(self):
        self.input_img = Input(name='input_img',
                               shape=(None, None, cfg.num_channels),
                               dtype='float32')
        # # use vgg16
        if cfg.backbone == 'vgg16':
            vgg16 = VGG16(input_tensor=self.input_img,
                          weights='imagenet',
                          include_top=False)
            if cfg.locked_layers:
                # locked first two conv layers
                locked_layers = [vgg16.get_layer('block1_conv1'),
                                 vgg16.get_layer('block1_conv2')]
                for layer in locked_layers:
                    layer.trainable = False
            self.f = [vgg16.get_layer('block%d_pool' % i).output
                      for i in cfg.feature_layers_range]

        # use resnet50
        elif cfg.backbone == 'resnet50':
            resnet50 = keras.applications.resnet50.ResNet50(include_top=False, weights='imagenet', input_tensor=self.input_img)
            if cfg.locked_layers:
                # locked first two conv layers
                # locked_layers = [vgg16.get_layer('block1_conv1'),
                #                  vgg16.get_layer('block1_conv2')]
                # for layer in locked_layers:
                #     layer.trainable = False
                pass
            activation_num = [49,40,22,10]
            self.f = [resnet50.get_layer('activation_%d' % i).output
                      for i in activation_num]

        self.f.insert(0, None)
        self.diff = cfg.feature_layers_range[0] - cfg.feature_layers_num

    def g(self, i):
        # i+diff in cfg.feature_layers_range
        assert i + self.diff in cfg.feature_layers_range, \
            ('i=%d+diff=%d not in ' % (i, self.diff)) + \
            str(cfg.feature_layers_range)
        if i == cfg.feature_layers_num:
            bn = BatchNormalization()(self.h(i))
            return Conv2D(32, 3, activation='relu', padding='same')(bn)
        else:
            return UpSampling2D((2, 2))(self.h(i))

    def h(self, i):
        # i+diff in cfg.feature_layers_range
        assert i + self.diff in cfg.feature_layers_range, \
            ('i=%d+diff=%d not in ' % (i, self.diff)) + \
            str(cfg.feature_layers_range)
        if i == 1:
            return self.f[i]
        else:
            concat = Concatenate(axis=-1)([self.g(i - 1), self.f[i]])
            bn1 = BatchNormalization()(concat)
            conv_1 = Conv2D(128 // 2 ** (i - 2), 1,
                            activation='relu', padding='same',)(bn1)
            bn2 = BatchNormalization()(conv_1)
            conv_3 = Conv2D(128 // 2 ** (i - 2), 3,
                            activation='relu', padding='same',)(bn2)
            return conv_3

    def east_network(self):
        inside_score = Conv2D(1, 1, padding='same', name='inside_score'
                              )(self.g(cfg.feature_layers_num))
        side_v_code = Conv2D(2, 1, padding='same', name='side_vertex_code'
                             )(self.g(cfg.feature_layers_num))
        side_v_coord = Conv2D(4, 1, padding='same', name='side_vertex_coord'
                              )(self.g(cfg.feature_layers_num))
        east_detect = Concatenate(axis=-1,
                                  name='east_detect')([inside_score,
                                                       side_v_code,
                                                       side_v_coord])
        return Model(inputs=self.input_img, outputs=east_detect)


if __name__ == '__main__':
    east = East()
    east_network = east.east_network()
    east_network.summary()
