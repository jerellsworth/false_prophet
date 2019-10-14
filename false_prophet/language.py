import functools
import glob
import itertools as it
import logging
import pickle
import os
import sys

import gensim
import nltk
from nltk.stem import PorterStemmer
from nltk.tokenize import sent_tokenize
from nltk.tokenize import word_tokenize

MODEL_MIN_CT = 5
MODEL_SIZE = 100
MODEL_WINDOW = 5
MODEL_CONFIDENCE_THRESH = 0.5

_LIB_DIR = os.path.dirname(os.path.realpath(__file__))
CORPUS_DIR = os.path.join(_LIB_DIR, 'corpus')
_CORPUS_PKL = os.path.join(CORPUS_DIR, 'corpus.pkl')
_MODEL_PKL = os.path.join(CORPUS_DIR, 'model.pkl')


def _cache(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if os.path.isfile(path):
                with open(path, 'rb') as f_pkl:
                    return pickle.load(f_pkl)
            r = func(*args, **kwargs)
            with open(path, 'wb') as f_pkl:
                pickle.dump(r, f_pkl)
            return r
        return wrapper
    return decorator

class _Model():

    def __init__(self):
        self.model = None
        self.porter_stemmer = PorterStemmer()

    def init_model(self):
        logging.info('initializing language model')
        nltk.download('punkt')
        self.model = self._get_model()

    def _word_clean(self, word):
        return self.porter_stemmer.stem(word.lower())

    def _corpus_tokenize(self, text):
        tokens = []
        for s in sent_tokenize(text):
            s_tokens = [self._word_clean(w) for w in word_tokenize(s)]
            tokens.append(s_tokens)
        return tokens

    @_cache(_CORPUS_PKL)
    def _get_corpus(self):
        texts = []
        for txt_file in glob.glob(os.path.join(CORPUS_DIR, '*.txt')):
            with open(txt_file) as fin:
                texts.append(fin.read())
        return self._corpus_tokenize('\n'.join(texts))

    @_cache(_MODEL_PKL)
    def _get_model(self):
        corpus = self._get_corpus()
        model = gensim.models.Word2Vec(
                corpus,
                min_count=MODEL_MIN_CT,
                size=MODEL_SIZE,
                window=MODEL_WINDOW)
        return model.wv

    def match(self, utterance, candidates):
        if self.model is None:
            self.init_model()
        tokens = it.chain.from_iterable(self._corpus_tokenize(utterance))
        candidates_processed = {self._word_clean(w): w for w in candidates}
        max_sim = 0
        winner = None
        for t in tokens:
            for c in candidates_processed.keys():
                try:
                    if t == c:
                        sim = 1.0
                    else:
                        sim = self.model.similarity(t, c)
                except KeyError:
                    sim = 0
                if sim > max_sim:
                    max_sim = sim
                    winner = candidates_processed[c]
        if max_sim < MODEL_CONFIDENCE_THRESH:
            return None
        return winner


MODEL = _Model()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--clean':
        print('cleaning')
        for pkl in (_CORPUS_PKL, _MODEL_PKL):
            if os.path.isfile(pkl):
                os.remove(pkl)

    def test_model(utterance, candidates):
        winner = MODEL.match(utterance, candidates)
        print('"{}" -> {}'.format(
            utterance,
            ', '.join((c if c != winner else '\033[1m{}\033[0m'.format(c)
                       for c in candidates))))
    candidates = ['battle', 'king']
    test_model('fight fight me', candidates)
    test_model('hello my lord', candidates)
    test_model('lets have a duel', candidates)
