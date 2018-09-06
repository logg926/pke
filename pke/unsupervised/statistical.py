# -*- coding: utf-8 -*-

"""Statistical keyphrase extraction models."""

from __future__ import absolute_import
from __future__ import division

import string
import math
import numpy
import re

from itertools import combinations
from collections import defaultdict

from pke.base import LoadFile
from pke.utils import load_document_frequency_file
from nltk.corpus import stopwords
from nltk.metrics import edit_distance


class TfIdf(LoadFile):
    """TF*IDF keyphrase extraction model.

    Parameterized example::

        import string
        import pke

        # 1. create a TfIdf extractor.
        extractor = pke.unsupervised.TfIdf(input_file='path/to/input.xml')

        # 2. load the content of the document.
        extractor.read_document(format='corenlp')

        # 3. select {1-3}-grams not containing punctuation marks as candidates.
        n = 3
        stoplist = list(string.punctuation)
        stoplist += ['-lrb-', '-rrb-', '-lcb-', '-rcb-', '-lsb-', '-rsb-']
        extractor.candidate_selection(n=n, stoplist=stoplist)

        # 4. weight the candidates using a `tf` x `idf`
        df = pke.load_document_frequency_file(input_file='path/to/df.tsv.gz')
        extractor.candidate_weighting(df=df)

        # 5. get the 10-highest scored candidates as keyphrases
        keyphrases = extractor.get_n_best(n=10)

    """

    def candidate_selection(self, n=3, stoplist=None):
        """Select 1-3 grams as keyphrase candidates.

        Args:
            n (int): the length of the n-grams, defaults to 3.
            stoplist (list): the stoplist for filtering candidates, defaults to
                `None`. Words that are punctuation marks from
                `string.punctuation` are not allowed.

        """

        # select ngrams from 1 to 3 grams
        self.ngram_selection(n=n)

        # initialize empty list if stoplist is not provided
        if stoplist is None:
            stoplist = []

        # filter candidates containing punctuation marks
        self.candidate_filtering(stoplist=list(string.punctuation) +
                                 ['-lrb-', '-rrb-', '-lcb-', '-rcb-', '-lsb-',
                                  '-rsb-'] +
                                  stoplist)


    def candidate_weighting(self, df=None):
        """Candidate weighting function using document frequencies.

        Args:
            df (dict): document frequencies, the number of documents should be
                specified using the "--NB_DOC--" key.
        """

        # initialize default document frequency counts if none provided
        if df is None:
            df = load_document_frequency_file(self._df_counts, delimiter='\t')

        # initialize the number of documents as --NB_DOC-- + 1 (current)
        N = 1 + df.get('--NB_DOC--', 0)

        # loop throught the candidates
        for k, v in self.candidates.items():

            # get candidate document frequency
            candidate_df = 1 + df.get(k, 0)

            # compute the idf score
            idf = math.log(N / candidate_df, 2)

            # add the idf score to the weights container
            self.weights[k] = len(v.surface_forms) * idf


class KPMiner(LoadFile):
    """KP-Miner keyphrase extraction model.

    This model was published and described in:

      * Samhaa R. El-Beltagy and Ahmed Rafea, KP-Miner: Participation in
        SemEval-2, *Proceedings of the 5th International Workshop on
        Semantic Evaluation*, pages 190-193, 2010.

    Parameterized example::

        import pke

        # 1. create a KPMiner extractor. 
        extractor = pke.unsupervised.KPMiner(input_file='path/to/input.xml',
                                             language='english')

        # 2. load the content of the document.
        extractor.read_document(format='corenlp')

        # 3. select {1-5}-grams that do not contain punctuation marks or
        #    stopwords as keyphrase candidates. Set the least allowable seen
        #    frequency to 5 and the number of words after which candidates are
        #    filtered out to 200.
        lasf = 5
        cutoff = 200
        extractor.candidate_selection(lasf=lasf, cutoff=cutoff)

        # 4. weight the candidates using KPMiner weighting function.
        df = pke.load_document_frequency_file(input_file='path/to/df.tsv.gz')
        alpha = 2.3
        sigma = 3.0
        extractor.candidate_weighting(df=df, alpha=alpha, sigma=sigma)

        # 5. get the 10-highest scored candidates as keyphrases
        keyphrases = extractor.get_n_best(n=10)

    """

    def candidate_selection(self, lasf=3, cutoff=400, stoplist=None):
        """ The candidate selection as described in the KP-Miner paper.

            Args:
                lasf (int): least allowable seen frequency, defaults to 3.
                cutoff (int): the number of words after which candidates are
                    filtered out, defaults to 400.
                stoplist (list): the stoplist for filtering candidates, defaults
                    to the nltk stoplist. Words that are punctuation marks from
                    string.punctuation are not allowed.
        """

        # select ngrams from 1 to 5 grams
        self.ngram_selection(n=5)

        # initialize stoplist list if not provided
        if stoplist is None:
            stoplist = stopwords.words(self.language)

        # filter candidates containing stopwords or punctuation marks
        self.candidate_filtering(stoplist=list(string.punctuation) +
                                 ['-lrb-', '-rrb-', '-lcb-', '-rcb-', '-lsb-',
                                  '-rsb-'] +
                                  stoplist)

        # further filter candidates using lasf and cutoff
        # Python 2/3 compatible
        for k in list(self.candidates):

            # get the candidate
            v = self.candidates[k]

            # delete if first candidate offset is greater than cutoff
            if v.offsets[0] > cutoff:
                del self.candidates[k]

            # delete if frequency is lower than lasf
            elif len(v.surface_forms) < lasf:
                del self.candidates[k]


    def candidate_weighting(self, df=None, sigma=3.0, alpha=2.3):
        """Candidate weight calculation as described in the KP-Miner paper.

        Note:
            w = tf * idf * B * P_f
            with
            
              * B = N_d / (P_d * alpha) and B = min(sigma, B)
              * N_d = the number of all candidate terms
              * P_d = number of candidates whose length exceeds one
              * P_f = 1

        Args:
            df (dict): document frequencies, the number of documents should
                be specified using the "--NB_DOC--" key.
            sigma (int): parameter for boosting factor, defaults to 3.0.
            alpha (int): parameter for boosting factor, defaults to 2.3.
        """

        # initialize default document frequency counts if none provided
        if df is None:
            df = load_document_frequency_file(self._df_counts, delimiter='\t')

        # initialize the number of documents as --NB_DOC-- + 1 (current)
        N = 1 + df.get('--NB_DOC--', 0)

        # compute the number of candidates whose length exceeds one
        P_d = sum([len(v.surface_forms) for v in self.candidates.values()
                   if len(v.lexical_form) > 1])

        # fall back to 1 if all candidates are words
        P_d = max(1, P_d)

        # compute the number of all candidate terms
        N_d = sum([len(v.surface_forms) for v in self.candidates.values()])

        # compute the boosting factor
        B = min(N_d / (P_d*alpha), sigma)

        # loop throught the candidates
        for k, v in self.candidates.items():

            # get candidate document frequency
            candidate_df = 1

            # get the df for unigram only
            if len(v.lexical_form) == 1:
                candidate_df += df.get(k, 0)

            # compute the idf score
            idf = math.log(N / candidate_df, 2)

            self.weights[k] = len(v.surface_forms) * B * idf


class YAKE(LoadFile):
    """YAKE keyphrase extraction model.

    This model was published and described in:

      * Ricardo Campos, Vítor Mangaravite, Arian Pasquali, Alípio Mário Jorge,
        Célia Nunes and Adam Jatowt.
        YAKE! Collection-Independent Automatic Keyword Extractor.
        *Proceedings of ECIR 2018.*, pages 806-810.

    Parameterized example::

        import pke
        from nltk.corpus import stopwords

        # 1. create a YAKE extractor.
        extractor = pke.unsupervised.YAKE(input_file='path/to/input.xml')

        # 2. load the content of the document.
        extractor.read_document(format='corenlp')

        # 3. select {1-3}-grams not containing punctuation marks and not
        #    beginning/ending with a stopword as candidates.
        stoplist = stopwords.words('english')
        extractor.candidate_selection(n=3, stoplist=stoplist)

        # 4. weight the candidates using YAKE weighting scheme, a window (in
        #    words) for computing left/right contexts can be specified.
        window = 2
        use_stems = False # use stems instead of words for weighting
        extractor.candidate_weighting(window=window,
                                      stoplist=stoplist,
                                      use_stems=use_stems)

        # 5. get the 10-highest scored candidates as keyphrases.
        #    redundant keyphrases are removed from the output using levenshtein
        #    distance and a threshold.
        threshold = 0.8
        keyphrases = extractor.get_n_best(n=10, threshold=threshold)

    """

    def __init__(self, input_file=None, language='english'):
        """ Redefining initializer for YAKE. """

        super(YAKE, self).__init__(input_file=input_file, language=language)

        self.words = defaultdict(set)
        """ Container for the vocabulary. """

        self.contexts = defaultdict(lambda: ([], []))
        """ Container for word contexts. """

        self.features = defaultdict(dict)
        """ Container for word features. """

        self.surface_to_lexical = {}
        """ Mapping from surface form to lexical form. """


    def candidate_selection(self, n=3, stoplist=None):
        """Select 1-3 grams as keyphrase candidates. Candidates beginning or
        ending with a stopword are filtered out. Words that do not contain
        at least one alpha-numeric character are not allowed.

        Args:
            n (int): the n-gram length, defaults to 3.
            stoplist (list): the stoplist for filtering candidates, defaults to
                the nltk stoplist.
        """

        # select ngrams from 1 to 3 grams
        self.ngram_selection(n=n)

        # filter candidates containing punctuation marks
        self.candidate_filtering(stoplist=list(string.punctuation) +
                                 ['-lrb-', '-rrb-', '-lcb-', '-rcb-', '-lsb-',
                                  '-rsb-'])

        # initialize empty list if stoplist is not provided
        if stoplist is None:
            stoplist = stopwords.words(self.language)

        # further filter candidates
        for k in list(self.candidates):

            # get the candidate
            v = self.candidates[k]

            # filter candidates starting/ending with a stopword
            if v.surface_forms[0][0].lower() in stoplist or \
               v.surface_forms[0][-1].lower() in stoplist:
                del self.candidates[k]


    def _vocabulary_building(self, use_stems=False):
        """Build the vocabulary that will be used to weight candidates. Only
        words containing at least one alpha-numeric character are kept.

        Args:
            use_stems (bool): whether to use stems instead of lowercase words
                for weighting, defaults to False.
        """

        # loop through sentences
        for i, sentence in enumerate(self.sentences):

            # compute the offset shift for the sentence
            shift = sum([s.length for s in self.sentences[0:i]])

            # loop through words in sentence
            for j, word in enumerate(sentence.words):

                # consider words containing at least one alpha-numeric character
                if self._is_alphanum(word) and \
                   not re.search('(?i)^-[lr][rcs]b-$', word):

                    # get the word or stem
                    index = word.lower()
                    if use_stems:
                        index = sentence.stems[j]

                    # add the word occurrence
                    self.words[index].add((shift+j, shift, i, word))


    def _contexts_building(self, use_stems=False, window=2):
        """Build the contexts of the words for computing the relatdeness
        feature. Words that occur within a window of n words are considered as
        context words.

        Args:
            use_stems (bool): whether to use stems instead of lowercase words
                for weighting, defaults to False.
            window (int): the size in words of the window used for computing
                co-occurrence counts, defaults to 2.
        """

        # loop through sentences
        for i, sentence in enumerate(self.sentences):

            # lowercase the words
            words = [w.lower() for w in sentence.words]

            # replace with stems if needed
            if use_stems:
                words = sentence.stems

            # loop through words in sentence
            for j, word in enumerate(words):

                # skip if word is not in vocabulary
                if word not in self.words:
                    continue

                # add the left context
                self.contexts[word][0].extend(
                    [w for w in words[max(0, j-window):j] if w in self.words]
                )

                # add the right context
                self.contexts[word][1].extend(
                    [w for w in words[j+1:min(len(words), j+window+1)]\
                     if w in self.words]
                )


    def _feature_extraction(self, stoplist=None):
        """Compute the weight of individual words using the following five
        features:

            1. CASING: gives importance to acronyms or words starting with a
               capital letter.

               CASING(w) = max(TF(U(w)), TF(A(w))) / (1 + log(TF(w)))

               with TF(U(w) being the # times the word starts with an uppercase
               letter, excepts beginning of sentences. TF(A(w)) is the # times
               the word is marked as an acronym.

            2. POSITION: gives importance to words occurring at the beginning of
               the document.

               POSITION(w) = log( log( 3 + Median(Sen(w)) ) )

               with Sen(w) contains the position of the sentences where w
               occurs.

            3. FREQUENCY: gives importance to frequent words.

               FREQUENCY(w) = TF(w) / ( MEAN_TF + STD_TF)

               with MEAN_TF and STD_TF computed on valid_tfs which are words
               that are not stopwords.

            4. RELATEDNESS: gives importance to words that do not have the
               characteristics of stopwords.

               RELATEDNESS(w) = 1 + (WR+WL)*(TF(w)/MAX_TF) + PL + PR

            5. DIFFERENT: gives importance to words that occurs in multiple
               sentences.

               DIFFERENT(w) = SF(w) / # sentences

               with SF(w) being the sentence frequency of word w.

        Args:
            stoplist (list): the stoplist for filtering candidates, defaults to
                the nltk stoplist.
        """

        # initialize stoplist list if not provided
        if stoplist is None:
            stoplist = stopwords.words(self.language)

        # get the Term Frequency of each word
        TF = [len(self.words[w]) for w in self.words]

        # get the Term Frequency of non-stop words
        TF_nsw = [len(self.words[w]) for w in self.words if w not in stoplist]

        # compute statistics
        mean_TF = numpy.mean(TF_nsw)
        std_TF = numpy.std(TF_nsw)
        max_TF = max(TF)

        # Loop through the words
        for word in self.words:

            # Term Frequency
            self.features[word]['TF'] = len(self.words[word])
            
            # Uppercase/Acronym Term Frequencies
            self.features[word]['TF_A'] = 0
            self.features[word]['TF_U'] = 0
            for (offset, shift, sent_id, surface_form) in self.words[word]:
                if surface_form.isupper() and len(word) > 1:
                    self.features[word]['TF_A'] += 1
                elif surface_form[0].isupper() and offset != shift:
                    self.features[word]['TF_U'] += 1

            # 1. CASING feature
            self.features[word]['CASING'] = max(self.features[word]['TF_A'],
                                                self.features[word]['TF_U'])
            self.features[word]['CASING'] /= 1.0 + math.log(
                                                self.features[word]['TF'])


            # 2. POSITION feature
            sentence_ids = list(set([t[2] for t in self.words[word]]))
            self.features[word]['POSITION'] = math.log(
                                             3.0 + numpy.median(sentence_ids))
            self.features[word]['POSITION'] = math.log(
                                              self.features[word]['POSITION'])

            # 3. FREQUENCY feature
            self.features[word]['FREQUENCY'] = self.features[word]['TF']
            self.features[word]['FREQUENCY'] /= (mean_TF + std_TF)

            # 4. RELATEDNESS feature
            self.features[word]['WL'] = 0.0
            if len(self.contexts[word][0]):
                self.features[word]['WL'] = len(set(self.contexts[word][0]))
                self.features[word]['WL'] /= len(self.contexts[word][0])
            self.features[word]['PL'] = len(set(self.contexts[word][0]))/max_TF

            self.features[word]['WR'] = 0.0
            if len(self.contexts[word][1]):
                self.features[word]['WR'] = len(set(self.contexts[word][1])) 
                self.features[word]['WR'] /= len(self.contexts[word][1])
            self.features[word]['PR'] = len(set(self.contexts[word][1]))/max_TF

            self.features[word]['RELATEDNESS'] = 1
            self.features[word]['RELATEDNESS'] += self.features[word]['PL']
            self.features[word]['RELATEDNESS'] += self.features[word]['PR']
            self.features[word]['RELATEDNESS'] += (self.features[word]['WR'] +\
                                                   self.features[word]['WL']) *\
                                            (self.features[word]['TF'] / max_TF)

            # 5. DIFFERENT feature
            self.features[word]['DIFFERENT'] = len(set(sentence_ids))
            self.features[word]['DIFFERENT'] /= len(self.sentences)

            # assemble the features to weight words
            A = self.features[word]['CASING']
            B = self.features[word]['POSITION']
            C = self.features[word]['FREQUENCY']
            D = self.features[word]['RELATEDNESS']
            E = self.features[word]['DIFFERENT']
            self.features[word]['weight'] = (D * B) / (A + (C / D) + (E / D))


    def candidate_weighting(self, window=2, stoplist=None, use_stems=False):
        """Candidate weight calculation as described in the YAKE paper.

        Args:
            stoplist (list): the stoplist for filtering candidates, defaults to
                the nltk stoplist.
            use_stems (bool): whether to use stems instead of lowercase words
                for weighting, defaults to False.
            window (int): the size in words of the window used for computing
                co-occurrence counts, defaults to 2.
        """

        # build the vocabulary
        self._vocabulary_building(use_stems=use_stems)

        # extract the contexts
        self._contexts_building(use_stems=use_stems, window=window)

        # compute the word features
        self._feature_extraction(stoplist=stoplist)

        # compute candidate weights
        for k, v in self.candidates.items():

            # use stems
            if use_stems:
                weights = [self.features[t]['weight'] for t in v.lexical_form]
                self.weights[k] = numpy.prod(weights)
                self.weights[k] /= len(v.offsets) * (1 + sum(weights))

            # use words
            else:
                lowercase_forms = [' '.join(t).lower() for t in v.surface_forms]
                for i, candidate in enumerate(lowercase_forms):
                    TF = lowercase_forms.count(candidate)
                    weights = [self.features[t.lower()]['weight'] for t \
                                in v.surface_forms[i]]
                    self.weights[candidate] = numpy.prod(weights)
                    self.weights[candidate] /= TF * (1 + sum(weights))
                    self.surface_to_lexical[candidate] = k


    def is_redundant(self, candidate, prev, threshold=0.8):
        """Test if one candidate is redundant with respect to a list of already
        selected candidates. A candidate is considered redundant if its
        levenshtein distance, with another candidate that is ranked higher in
        the list, is greater than a threshold.

        Args:
            candidate (str): the lexical form of the candidate.
            prev (list): the list of already selected candidates.
            threshold (float): the threshold used when computing the
                levenshtein distance, defaults to 0.8.
        """

        # loop through the already selected candidates
        for prev_candidate in prev:
            dist = edit_distance(candidate, prev_candidate)
            dist /= max(len(candidate), len(prev_candidate))
            if (1.0 - dist) > threshold:
                return True
        return False


    def get_n_best(self,
                   n=10,
                   redundancy_removal=True,
                   stemming=False,
                   threshold=0.8):
        """ Returns the n-best candidates given the weights.

            Args:
                n (int): the number of candidates, defaults to 10.
                redundancy_removal (bool): whether redundant keyphrases are
                    filtered out from the n-best list using levenshtein
                    distance, defaults to True.
                stemming (bool): whether to extract stems or surface forms
                    (lowercased, first occurring form of candidate), default to
                    stems.
                threshold (float): the threshold used when computing the
                    levenshtein distance, defaults to 0.8.
        """

        # sort candidates by ascending weight
        best = sorted(self.weights, key=self.weights.get, reverse=False)

        # remove redundant candidates
        if redundancy_removal:

            # initialize a new container for non redundant candidates
            non_redundant_best = []

            # loop through the best candidates
            for candidate in best:

                # test wether candidate is redundant
                if self.is_redundant(candidate, non_redundant_best):
                    continue

                # add the candidate otherwise
                non_redundant_best.append(candidate)

                # break computation if the n-best are found
                if len(non_redundant_best) >= n:
                    break

            # copy non redundant candidates in best container
            best = non_redundant_best

        # get the list of best candidates as (lexical form, weight) tuples
        n_best = [(u, self.weights[u]) for u in best[:min(n, len(best))]]

        # replace with surface forms if no stemming
        if stemming:
            for i, (candidate, weight) in enumerate(n_best):

                if candidate not in self.candidates:
                    candidate = self.surface_to_lexical[candidate]

                candidate = ' '.join(self.candidates[candidate].lexical_form)
                n_best[i] = (candidate, weight)

        # return the list of best candidates
        return n_best
