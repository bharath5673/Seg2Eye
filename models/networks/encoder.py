"""
Copyright (C) 2019 NVIDIA Corporation.  All rights reserved.
Licensed under the CC BY-NC-SA 4.0 license (https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode).
"""
import numpy as np
import torch.nn as nn
import torch.nn.functional as F

from models.networks.base_network import BaseNetwork
from models.networks.normalization import get_nonspade_norm_layer


class ConvEncoder(BaseNetwork):
    """ Same architecture as the image discriminator """

    def __init__(self, opt):
        super().__init__()

        kw = 3
        pw = int(np.ceil((kw - 1.0) / 2))
        ndf = opt.ngf
        norm_layer = get_nonspade_norm_layer(opt, opt.norm_E)
        layer1 = norm_layer(nn.Conv2d(1, ndf, kw, stride=2, padding=pw))
        layer2 = norm_layer(nn.Conv2d(ndf * 1, ndf * 2, kw, stride=2, padding=pw))
        layer3 = norm_layer(nn.Conv2d(ndf * 2, ndf * 4, kw, stride=2, padding=pw))
        layer4 = norm_layer(nn.Conv2d(ndf * 4, ndf * 8, kw, stride=2, padding=pw))
        layer5 = norm_layer(nn.Conv2d(ndf * 8, ndf * 8, kw, stride=2, padding=pw))

        sequence = list()
        for layer in [layer1,
                      layer2,
                      layer3,
                      layer4,
                      layer5]:
            sequence.append(layer)

        if opt.crop_size >= 256:
            layer6 = norm_layer(nn.Conv2d(ndf * 8, ndf * 8, kw, stride=2, padding=pw))
            sequence.append(layer6)

        self.len_sequence = len(sequence)
        for n in range(self.len_sequence):
            self.add_module('layer' + str(n), nn.Sequential(*sequence[n]))

        self.so = s0 = 4

        self.fc_mu = nn.Linear(ndf * 8 * s0 * s0, opt.w_dim)
        self.fc_var = nn.Linear(ndf * 8 * s0 * s0, opt.w_dim)

        self.actvn = nn.LeakyReLU(0.2, False)
        self.opt = opt

    def forward(self, x, get_intermediate_features=False):
        if x.size(2) != 256 or x.size(3) != 256:
            x = F.interpolate(x, size=(256, 256), mode='bilinear')

        results = [x]
        for i, submodel in enumerate(self.children()):
            if i < self.len_sequence:
                # We only want to iterate through the convolutional layers in sequence
                intermediate_output = submodel(results[-1])
                results.append(intermediate_output)

        features = results[1:]
        x_out = results[-1]

        out = self.actvn(x_out)

        out = out.view(out.size(0), -1)
        mu = self.fc_mu(out)
        logvar = self.fc_var(out)

        return mu, logvar, features
