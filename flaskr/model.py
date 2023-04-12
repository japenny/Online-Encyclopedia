raise ValueError('!!! Run the model in google colab !!!')

### Imports ###

""" Datasets """
from datasets import load_dataset, load_dataset_builder
import gensim.downloader as api

""" Tensorflow/Keras """
import tensorflow
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau, TensorBoard
from tensorflow.keras.layers import Attention, Bidirectional, Concatenate, Dense, Embedding, Flatten, Input, LayerNormalization, LSTM, MultiHeadAttention
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam, SGD
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.preprocessing.text import Tokenizer, tokenizer_from_json
from tensorflow.keras.regularizers import *

""" TF Cloud Training """
import tensorflow_cloud as tfc
from tensorflow_cloud.core.docker_config import DockerConfig

""" Data processing/visualization """
import nltk
from nltk.corpus import stopwords
nltk.download('stopwords')
import numpy as np
import pandas as pd
import re

""" Cloud """
from google.colab import auth
from google.cloud import storage

""" Other """
import io
import sys
import os

##############################################

"""

Originally ran in Google Colab

"""

##############################################

### Load data ###

""" Check Data """
ds_name = 'cnn_dailymail' # 'GEM/wiki_lingua' 'ccdv/pubmed-summarization' 'scientific_papers'
ds_sub = '3.0.0'
builder = load_dataset_builder(ds_name, ds_sub)

print(builder.info.description)
builder.info.features

""" Load Dataset """
dataset = load_dataset(ds_name, ds_sub)

train_len = len(dataset['train']['article'])
val_len = len(dataset['validation']['article'])

if not tfc.remote():
    split_train = 100
    split_val = 100

st = 1

""" Split Data and add sos/eos tokens """
sos_token = '<sos>'
eos_token = '<eos>'

x_train = np.array([f'{sos_token} {art} {eos_token}' for art in dataset['train']['article'][:split_train]])
y_train = np.array([f'{sos_token} {sum} {eos_token}' for sum in dataset['train']['highlights'][:split_train]])

x_val = np.array([f'{sos_token} {art} {eos_token}' for art in dataset['validation']['article'][:split_val]])
y_val = np.array([f'{sos_token} {sum} {eos_token}' for sum in dataset['validation']['highlights'][:split_val]])

x_train = np.concatenate([x_train, x_val], axis=0)
y_train = np.concatenate([y_train, y_val], axis=0)

del x_val, y_val

x_test = np.array([f'{sos_token} {art} {eos_token}' for art in dataset['test']['article']])
y_test = np.array([f'{sos_token} {sum} {eos_token}' for sum in dataset['test']['highlights']])

print(f'x_train shape: {x_train.shape}, y_train shape: {y_train.shape}')

""" Data Samples """
df = pd.DataFrame({'Article':x_train[:5], 'Summary':y_train[:5]})
df.head()

del dataset, df

### Clean and process data ###

""" Get stop words"""
stop_words = stopwords.words('english')
stop_words.extend(['cnn', 'reuters'])

""" Lowercase all words """
x_train, y_train = np.char.lower(x_train), np.char.lower(y_train)
x_test, y_test = np.char.lower(x_test), np.char.lower(y_test)

""" Remove stop words """
pattern = re.compile("\\b(" + "|".join(stop_words) + ")\\b")

vec_pattern = np.vectorize(lambda text:pattern.sub('', text))
x_train = vec_pattern(x_train)
y_train = vec_pattern(y_train)

del pattern, stop_words, vec_pattern

""" Tokenize data """
tokenizer = Tokenizer(filters='"#$%&()*+,-/:;=@[\\]^_`{|}~\t\n', oov_token="<unk>")

tokenizer.fit_on_texts(x_train)

x_train, y_train = tokenizer.texts_to_sequences(x_train), tokenizer.texts_to_sequences(y_train)
x_test, y_test = tokenizer.texts_to_sequences(x_test), tokenizer.texts_to_sequences(y_test)

""" Pad tokenized data """
x_train, y_train = pad_sequences(x_train, padding='post'), pad_sequences(y_train, padding='post')
x_test, y_test = pad_sequences(x_test, padding='post'), pad_sequences(y_test, padding='post')

""" After Processing Data Samples """
df = pd.DataFrame(x_train[:3])
df.head()

del df

### ###
""" Load Pre-Trained Word Embeddings """
w2v_model = api.load('word2vec-google-news-300')

""" Create Embedding Matrix """
vocab_dim = len(tokenizer.word_index)+1
emb_dim = 300
x_row, x_col = x_train.shape
y_row, y_col = y_train.shape

emb_matrix = np.zeros((vocab_dim, emb_dim))

for word, idx in tokenizer.word_index.items():
  if word in w2v_model:
    emb_matrix[idx] = w2v_model[word]

del w2v_model

""" Develop Model """
def get_model(lat_0=128, lat_1=128, 
              dr_0=0.35, dr_1=0.35, dr_2=0.35,
              att_0=2, att_1=2, 
              beam_width=4,
              vocab_len=vocab_dim, emb_len=emb_dim):

    # Encoder
    encoder_input     = Input(shape=(None,), name='Input_0')
    encoder_emb_layer = Embedding(vocab_len, emb_len, weights=[emb_matrix], trainable=False, name='Embedding_0')
    encoder_emb_input = encoder_emb_layer(encoder_input)
    encoder_lstm_0    = Bidirectional(LSTM(units=lat_0, dropout=dr_0, return_sequences=True, return_state=True), name='Bidirectional_LSTM_0')
    encoder_emb_0     = encoder_lstm_0(encoder_emb_input)
    encoder_lstm_1    = Bidirectional(LSTM(units=lat_1, dropout=dr_1, return_sequences=True, return_state=True), name='Bidirectional_LSTM_1')
    encoder_out, forward_h, forward_c, backward_h, backward_c = encoder_lstm_1(encoder_emb_0[0])
    encoder_lay_norm  = LayerNormalization(name='Layer_Norm_0')
    encoder_emb_norm  = encoder_lay_norm(encoder_out)
    encoder_self_att  = MultiHeadAttention(num_heads=att_0, key_dim=emb_len, name='Attention_0')
    encoder_att_out   = encoder_self_att(encoder_emb_norm, encoder_emb_norm)
    forward_h_concat  = Concatenate(name='Concat_0')([forward_h, backward_h])
    forward_c_concat  = Concatenate(name='Concat_1')([forward_c, backward_c])
    encoder_states    = [forward_h_concat, forward_c_concat]

    # Decoder
    decoder_input     = Input(shape=(None,), name='Input_1')
    decoder_emb_layer = Embedding(vocab_len, emb_len, weights=[emb_matrix], trainable=False, name='Embedding_1')
    decoder_emb_out   = decoder_emb_layer(decoder_input)
    decoder_lstm      = LSTM(units=lat_1*2, dropout=dr_2, return_sequences=True, return_state=True, name='LSTM_0')
    decoder_out,_,_   = decoder_lstm(decoder_emb_out, initial_state=encoder_states)
    decoder_multi_att = MultiHeadAttention(num_heads=att_1, key_dim=emb_len, name='Attention_1')
    decoder_att_out   = decoder_multi_att(query=decoder_out, value=encoder_att_out)
    decoder_dense     = Dense(vocab_len, activation='softmax', name='Dense_0')
    decoder_dense_out = decoder_dense(decoder_att_out)
    
    # Create model
    model = Model([encoder_input, decoder_input], decoder_dense_out, name='Text_Summarization_Model')

    return model

""" Create Callbacks """
def get_callbacks(tb_path, cp_path, 
                  rlr_factor=0.015, rlr_patience=3, 
                  es_patience=6):
  
    early_stop   = EarlyStopping(monitor='val_accuray', patience=es_patience)
    reduce_lr    = ReduceLROnPlateau(factor=rlr_factor, patience=rlr_patience)
    tensor_board = TensorBoard(log_dir=tb_path)
    model_cp     = ModelCheckpoint(filepath=cp_path,
                                   monitor='val_accuracy',
                                   save_best_only=True,
                                   save_freq='epoch',
                                   verbose=1)
  
    return early_stop, model_cp, reduce_lr, tensor_board

""" Compile Model """
def compile_model(model, lr=0.001):
    opt = Adam(lr)
    # met_rl = RougeL()

    model.compile(optimizer=opt,
                    loss='sparse_categorical_crossentropy')#, metrics=['accuracy'])
                    # metrics=[met_rl, 'accuracy'])

### Run model ###

""" Create paths """
GCP_PROJECT_ID = 'model-training-383203'
GCS_BUCKET  = 'model_sum'
REGION = 'us-central1'
JOB_NAME = 'temp_model'
AUTH_JSON = '/content/model-training-383203-38e4420de909.json'
REQUIRE = 'model-require.txt'

GCS_BASE_PATH = f'gs://{GCS_BUCKET}/{JOB_NAME}'
TENSORBOARD_LOGS = os.path.join(GCS_BASE_PATH,"logs")
MODEL_CP = os.path.join(GCS_BASE_PATH,"checkpoints")
SAVED_MODEL_DIR = os.path.join(GCS_BASE_PATH,"saved_model")
TOKENIZE_DIR = os.path.join(GCS_BASE_PATH, 'tokenizer')

""" Authorize user """
if not tfc.remote():
  if "google.colab" in sys.modules:
      auth.authenticate_user()
      os.environ["GOOGLE_CLOUD_PROJECT"] = GCP_PROJECT_ID 
      os.environ["GCS_BUCKET"] = GCS_BUCKET
      os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = AUTH_JSON

""" Get and Set up model"""
model = get_model()
compile_model(model)
callbacks = get_callbacks(TENSORBOARD_LOGS, MODEL_CP)

""" Run model if in cloud """
if tfc.remote():
    history = model.fit([x_train, y_train[:,:-1]], y_train[:,1:], 
                        validation_split=0.25, 
                        batch_size=128, epochs=100,
                        callbacks=callbacks)
    
else:
    history = model.fit([x_train[:split_train], y_train[:split_train][:,:-1]], y_train[:split_train][:,1:], 
                        validation_split=0.25, 
                        batch_size=50, epochs=50,
                        callbacks=callbacks)

""" Save model parameters """
model.save(SAVED_MODEL_DIR)

storage_client = storage.Client()
bucket = storage_client.bucket(GCS_BUCKET)
blob = bucket.blob(TOKENIZE_DIR)
token_json = tokenizer.to_json()

with open('tokenizer.json', 'w') as f:
  f.write(token_json)

blob.upload_from_filename('tokenizer.json')

""" Run model on cloud """
docker = DockerConfig(image_build_bucket=GCS_BUCKET)
# entry_point = path
tfc.run(
        requirements_txt=REQUIRE,
        distribution_strategy="auto",
        docker_config=docker
)

