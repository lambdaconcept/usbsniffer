#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2019 / LambdaConcept  / po@lambdaconcept.com

from migen import *

class TuneClocker(Module):
    def __init__(self, tuning_word):
        self.en = Signal()

        # # #

        acc = Signal(32)

        self.sync += [
            Cat(acc, self.en).eq(acc + tuning_word),
        ]
