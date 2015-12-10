import DiskPredictionModel as ls
import ReadInputCSVFile as rd
import pandas as pd
import numpy as np
from pyspark import SparkContext, SparkConf
from elephas.utils.rdd_utils import to_simple_rdd
from elephas.spark_model import SparkModel
from elephas import optimizers as elephas_optimizers
import elephas.spark_model as sm
import os
from os.path import basename

def getSMARTParameters():
    filePointer = open("/home/user/Desktop/Cloud/ModelConfigFile.txt", "r+")
    SMARTParameterList=[]
    for line in filePointer:
        line = line.replace("\n","")
        parm = line.split(",")
        SMARTParameterList.append(modelName)
    return SMARTParameterList

# Application Main function
def main(modelName):
    timeSteps= 30                                                                   # No of past values that has to be used for Training purpose
    #Initializing Spark Configuration for the Master Node
    config = SparkConf().setAppName('DiskDetection_App')
    config.setMaster('local[6]')                                                    #indicates the number of threads on the master node
    sc = SparkContext(conf=config)                                                  # Initializing the Spark Context
    print "Going to Initialize the LSTM model"
    lstm = ls.cloudLSTM()                                                           # Initializing the DiskPrediction Model(LSTM Model)
    print "Initialized the Model"
    lstmModel = lstm.get_LSTM_Model(getSMARTParameters,timeSteps)                   # Obtaining the LSTM model for initializing SparkModel Class
    trainSize= 0.2                                                                  # Fraction of input used for Training purpose
    acc = 0.0                                                                       # Model accuracy
    inputFilePath = os.environ.get('DATA_FILE_PATH')                                # Get the Input CSV filepath from environment
    year=sys.argv[1]                                                                # get the year from the Command Line arguments
    month=sys.argv[2]                                                               # get the month from the Command Line arguments
    inputFilePath=inputFilePath+"/"+str(year)+"/"+str(year)+"-"+str(month)+"*.csv"  # For E.g "/home/user/Desktop/Cloud/Test/2014/2014-11*.csv"
    print("InputPath",inputFilePath)
    flowV= rd.generate_DataFrame(inputFilePath,getSMARTParameters())
    inputCSVFilePath = os.environ.get('MODEL_CSV_FILEPATH')+str(modelName)+".csv"    # For E.g "/hadoop/elephas/Output/ST4000DM000.csv"

    modelFeatures = pd.read_csv(filepath_or_buffer=inputCSVFilePath,usecols=getSMARTParameters)
    modelLabel = pd.read_csv(filepath_or_buffer=inputCSVFilePath,usecols=['failure'])   #"/hadoop/elephas/Output/ST4000DM000.csv"

    # Removing Not A Number values from the Input Dataframe
    modelFeatures = modelFeatures.fillna(0)
    modelLabel = modelLabel.fillna(0)

    # Obtaining 3D training and testing vectors
    (feature_train, label_train), (feature_test, label_test) = lstm.train_test_split(modelFeatures,modelLabel,trainSize,timeSteps)

    # Initializing the Adam Optimizer for Elephas
    adam = elephas_optimizers.Adam()
    print "Adam Optimizer initialized"
    #Converting Dataframe to Spark RDD
    rddataset = to_simple_rdd(sc, feature_train, label_train)
    print "Training data converted into Resilient Distributed Dataset"
    #Initializing the SparkModel with Optimizer,Master-Worker Mode and Number of Workers
    spark_model = SparkModel(sc,lstmModel,optimizer=adam ,frequency='epoch', mode='asynchronous', num_workers=2)
    print "Spark Model Initialized"
    #Initial training run of the model
    spark_model.train(rddataset, nb_epoch=10, batch_size=200, verbose=1, validation_split=0)
    # Saving the model
    score, acc = spark_model.evaluate(feature_test, label_test,show_accuracy=True)
    while(acc <= 0.6):
        # Training the Input Data set
        spark_model.train(rddataset, nb_epoch=10, batch_size=200, verbose=1, validation_split=0)
        print "LSTM model training done !!"
        score, acc = spark_model.evaluate(feature_test, label_test,show_accuracy=True)
    print "Saving weights!!"
    spark_model.save_weights("/home/vyassu/my_model_weights.h5")
    print "LSTM model testing commencing !!"
    predicted1=spark_model.predict_classes(feature_test)
    df_confusion = pd.crosstab(label_test.flatten(), predicted1.flatten(), rownames=['Actual'], colnames=['Predicted'], margins=True)
    print df_confusion

if __name__ == '__main__':
   count=0
   for i in os.listdir(os.environ.get("MODEL_CSV_FILEPATH")):
       if count == 0:
          modelName = os.path.splitext(i)[0]
          main(modelName)
          count+=1