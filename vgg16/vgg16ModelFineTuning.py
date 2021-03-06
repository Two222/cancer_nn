import numpy as np
import matplotlib.pyplot as plt
import numpy as np

import tensorflow as tf

from keras import backend as K
from keras.layers import Input
from keras.layers import Conv2D
from keras.layers import MaxPooling2D
from keras.models import Model
from keras.utils.data_utils import get_file
from keras import optimizers
from keras import applications
from keras import regularizers
from keras.models import Sequential
from keras.layers import Input, Dropout, Flatten, Dense
from keras.preprocessing.image import ImageDataGenerator 
img_width, img_height = 224, 224

top_model_weights_path = "isic-vgg16-transfer-learning-07-l2-300e.h5"

train_data_dir = '../data/train'
validation_data_dir = '../data/validation'

train_aug_data_dir = '../data/aug/train'
validation_aug_data_dir = "../data/aug/validation"

nb_train_samples = 9216
nb_validation_samples = 2304

epochs = 10

batch_size = 16

def getDataGenObject ( directory, class_mode ):

    datagen = ImageDataGenerator(
        rescale = 1./255,
        # rotation_range = 40,
        # width_shift_range = 0.1,
        # height_shift_range = 0.1,
        # shear_range = 0.1,
        # zoom_range = 0.1,
        # horizontal_flip = True,
        # fill_mode = "nearest"
    )

    datagen_generator = datagen.flow_from_directory(
        directory,
        target_size = (img_height, img_width),
        batch_size = batch_size,
        class_mode = class_mode,
        shuffle = False
    )

    return datagen_generator

def getTrainDataGenObject( path = train_aug_data_dir, class_mode = None ):

    return getDataGenObject( path, class_mode )

def getValidationDataGenObject( path = validation_aug_data_dir, class_mode = None ):

    return getDataGenObject( path, class_mode )




def saveIntermediateTransferValues( layer_name = "block4_pool" ):

    model = applications.VGG16( include_top = False, weights = "imagenet")

    for layer in model.layers:
        print layer.name

    intermediate_model = Model( 
        inputs = model.input,
        outputs = model.get_layer(layer_name).output
    )

    train_transfer_values = intermediate_model.predict_generator(

        getTrainDataGenObject(),
        nb_train_samples // batch_size,
        verbose = 1

    )

    print ( "Train transfer Values shape {0}".format(train_transfer_values.shape) )
    np.save( open("train_transfer_intermediate_values.npy", "w"), train_transfer_values )

    validation_transfer_values = intermediate_model.predict_generator(

        getValidationDataGenObject(),
        nb_validation_samples // batch_size,
        verbose = 1
    )

    print ( "Validation transfer Values shape {0}".format(validation_transfer_values.shape) )
    np.save( open("validation_transfer_intermediate_values.npy", "w"), validation_transfer_values )

def toTensor( np_array ):
    
    return tf.convert_to_tensor( np_array, np.float32 )

def toKerasTensor( input_tensor ):

    if K.is_keras_tensor( input_tensor ):
        return input_tensor
    else:
        return Input( tensor = input_tensor, shape = input_tensor.shape)

def plotTraining(history):
    # list all data in history
    print(history.history.keys())


    # summarize history for accuracy
    plt.plot(history.history['acc'])
    plt.plot(history.history['val_acc'])
    plt.title('model accuracy')
    plt.ylabel('accuracy')
    plt.xlabel('epoch')
    plt.legend(['train', 'test'], loc='upper left')
    plt.show()


    # summarize history for loss
    plt.plot(history.history['loss'])
    plt.plot(history.history['val_loss'])
    plt.title('model loss')
    plt.ylabel('loss')
    plt.xlabel('epoch')
    plt.legend(['train', 'test'], loc='upper left')
    plt.show()


def VGG16ConvBlockFive( pretrained_weights ):

    input_img = Input( shape = ( 14, 14, 512 ) )

    x = Conv2D(512, (3, 3), activation='relu', padding='same', name='block5_conv1')( input_img )
    x = Conv2D(512, (3, 3), activation='relu', padding='same', name='block5_conv2')(x)
    x = Conv2D(512, (3, 3), activation='relu', padding='same', name='block5_conv3')(x)
    x = MaxPooling2D((2, 2), strides=(2, 2), name='block5_pool')(x)
    WEIGHTS_PATH_NO_TOP = 'https://github.com/fchollet/deep-learning-models/releases/download/v0.1/vgg16_weights_tf_dim_ordering_tf_kernels_notop.h5'

    model = Model( input_img, x )

    if pretrained_weights :
        print "pretrained conv_block_5 weights loading"
        weights_path = get_file(
            'vgg16_weights_tf_dim_ordering_tf_kernels_notop.h5',
            WEIGHTS_PATH_NO_TOP,
            cache_subdir='models'
        )
        model.load_weights( weights_path, by_name = True )

    return model

def FCC( pretrained_weights ):
    
    model = Sequential()
    model.add(Flatten(input_shape = (7, 7, 512) ))
    model.add(Dense(100, activation = "relu"))
    model.add(Dropout(0.3))
    model.add(Dense(1, activation = "sigmoid"))

    if pretrained_weights:
        print "pretrained FCC weights loading"
        model.load_weights( 'isic-vgg16-transfer-learning.h5' )

    return model


def vgg16FromScratch():

    model = applications.VGG16(include_top = False, weights = None, input_shape = (224, 224, 3))

    return model


def initModel( fine_tune = True ):


    weights_path = 'fine-tune-vgg16.h5'

    #load model
    if fine_tune :
        #load data
        print ( "loading intermediate transfer values" )
        train_data = np.load( 'train_transfer_intermediate_values.npy' )
        train_labels = np.array( [0] *  (nb_train_samples / 2) + [1] * (nb_train_samples / 2))
        validation_data = np.load(open("validation_transfer_intermediate_values.npy"))
        validation_labels = np.array( [0] * (nb_validation_samples / 2) + [1] * (nb_validation_samples / 2))

        print ("loading conv block 5")
        model = VGG16ConvBlockFive( False )
        

    else:
        weights_path = 'scratch-vgg16.h5'
        model = vgg16FromScratch()



    print ("loading FCC")
    top_model = FCC( True )

    print( "combining")
    model = Model( input = model.input, output = top_model( model.output ) )



    model.compile(loss='binary_crossentropy',
        optimizer=optimizers.SGD(lr=1e-4, momentum=0.9),
        #optimizer = optimizers.RMSprop( lr = 1e-2 ),
        #optimizer = optimizers.Adam( lr = 1e-2 ),
        metrics=['accuracy']
    )

    if fine_tune:
        history = model.fit(train_data, train_labels, 
            epochs = epochs, 
            batch_size = batch_size, 
            validation_data = (validation_data, validation_labels),
            shuffle = True
           #callbacks = callbacks_list
        )
    else:
        history = model.fit_generator(
            getTrainDataGenObject( class_mode = 'binary' ),
            epochs = epochs,
            steps_per_epoch = nb_train_samples // batch_size,
            validation_data = getValidationDataGenObject( class_mode = 'binary' ),
            validation_steps = nb_validation_samples // batch_size,
        )




    model.save_weights(weights_path)

    # plot Training
    plotTraining(history)
    


def main():
    #saveIntermediateTransferValues();    
    initModel( fine_tune = False )
    
if __name__ == '__main__':
    main()
