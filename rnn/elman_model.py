__author__ = 'heni'

import pickle
import theano
import numpy
import os

from theano import tensor as T
from collections import OrderedDict


class Elman(object):
    def __init__(self, nh, nc, ne, de, cs):
        '''
        nh :: dimension of the hidden layer
        nc :: number of classes
        ne :: number of word embeddings in the vocabulary
        de :: dimension of the word embeddings
        cs :: word window context size
        '''

        self.hyperParams = {
            'nh': nh,
            'nc': nc,
            'ne': ne,
            'de': de,
            'cs': cs
        }

    def setup(self):
        self.setupParams()
        self.buildModel()

    def setupParams(self):
        nh = self.hyperParams['nh']
        nc = self.hyperParams['nc']
        ne = self.hyperParams['ne']
        de = self.hyperParams['de']
        cs = self.hyperParams['cs']

        # parameters
        self.emb = theano.shared(0.2 * numpy.random.uniform(-1.0, 1.0,
                                                            (ne + 1, de)).astype(
                                                                theano.config.floatX))  # add one for PADDING at the end
        self.Wx = theano.shared(0.2 * numpy.random.uniform(-1.0, 1.0,
                                                           (de * cs, nh)).astype(theano.config.floatX))
        self.Wh = theano.shared(0.2 * numpy.random.uniform(-1.0, 1.0,
                                                           (nh, nh)).astype(theano.config.floatX))
        self.W = theano.shared(0.2 * numpy.random.uniform(-1.0, 1.0,
                                                          (nh, nc)).astype(theano.config.floatX))
        self.bh = theano.shared(numpy.zeros(nh, dtype=theano.config.floatX))
        self.b = theano.shared(numpy.zeros(nc, dtype=theano.config.floatX))
        self.h0 = theano.shared(numpy.zeros(nh, dtype=theano.config.floatX))

        # bundle
        self.params = [self.emb, self.Wx, self.Wh, self.W, self.bh, self.b, self.h0]
        self.names = ['emb', 'Wx', 'Wh', 'W', 'bh', 'b', 'h0']

    def buildModel(self):
        idxs = T.imatrix()  # as many columns as context window size/lines as words in the sentence
        x = self.emb[idxs].reshape((idxs.shape[0], self.hyperParams['de'] * self.hyperParams['cs']))
        y = T.iscalar('y')  # label

        def recurrence(x_t, h_tm1):
            h_t = T.nnet.sigmoid(T.dot(x_t, self.Wx) + T.dot(h_tm1, self.Wh) + self.bh)
            s_t = T.nnet.softmax(T.dot(h_t, self.W) + self.b)
            return [h_t, s_t]

        [h, s], _ = theano.scan(fn=recurrence,
                                sequences=x, outputs_info=[self.h0, None],
                                n_steps=x.shape[0])

        p_y_given_x_lastword = s[-1, 0, :]
        p_y_given_x_sentence = s[:, 0, :]
        y_pred = T.argmax(p_y_given_x_sentence, axis=1)

        # cost and gradients and learning rate
        lr = T.scalar('lr')
        nll = -T.mean(T.log(p_y_given_x_lastword)[y])
        gradients = T.grad(nll, self.params)
        updates = OrderedDict((p, p - lr * g) for p, g in zip(self.params, gradients))

        # theano functions
        self.classify = theano.function(inputs=[idxs], outputs=y_pred)

        self.train = theano.function(inputs=[idxs, y, lr],
                                     outputs=nll,
                                     updates=updates)

        self.normalize = theano.function(inputs=[],
                                         updates={self.emb:
                                                      self.emb / T.sqrt((self.emb ** 2).sum(axis=1)).dimshuffle(0,
                                                                                                                'x')})

    def save(self, folder):
        files = []
        for param, name in zip(self.params, self.names):
            file = os.path.join(folder, name + '.npy')
            numpy.save(file, param.get_value())
            files.append(name + '.npy')
        base = {
            'names': self.names,
            'files': files,
            'hyperParams': self.hyperParams
        }
        pickle.dump(base, open(os.path.join(folder, 'elman.pickle'), 'wb'))

    @staticmethod
    def load(folder):
        base = pickle.load(open(os.path.join(folder, 'elman.pickle'), 'rb'))
        names = base['names']
        files = base['files']
        hyperParams = base['hyperParams']
        print(hyperParams)

        elman = Elman(hyperParams['nh'], hyperParams['nc'], hyperParams['ne'], hyperParams['de'], hyperParams['cs'])
        elman.names = names
        loadedParams = []
        for name, file in zip(names, files):
            param = theano.shared(numpy.load(os.path.join(folder, file)))
            loadedParams.append(param)
            setattr(elman, name, param)
        elman.params = loadedParams

        elman.buildModel()

        return elman