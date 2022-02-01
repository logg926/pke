from distutils.core import setup

setup(name='pkelambda',
      version='1.8.1',
      description='Python Keyphrase Extraction module',
      author='pkelambda contributors',
      author_email='florian.boudin@univ-nantes.fr',
      license='gnu',
      packages=['pkelambda', 'pkelambda.unsupervised', 'pkelambda.supervised',
                'pkelambda.supervised.feature_based', 'pkelambda.unsupervised.graph_based',
                'pkelambda.unsupervised.statistical', 'pkelambda.supervised.neural_based'],
      url="https://github.com/boudinfl/pke",
      install_requires=[
          'nltk',
          'networkx',
          'numpy',
          'scipy',
          'spacy',
          'six',
          'sklearn',
          'unidecode',
          'future',
          'joblib'
      ],
      package_data={'pkelambda': ['models/*.pickle', 'models/*.gz']}
      )
