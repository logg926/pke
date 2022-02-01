# -*- coding: utf-8 -*-
# Python Keyphrase Extraction toolkit: unsupervised models

from __future__ import absolute_import

from pkelambda.supervised.api import SupervisedLoadFile
from pkelambda.supervised.feature_based.kea import Kea
from pkelambda.supervised.feature_based.topiccorank import TopicCoRank
from pkelambda.supervised.feature_based.wingnus import WINGNUS
from pkelambda.supervised.neural_based.seq2seq import Seq2Seq
