#Purpose: Find Natural Breaks in data using Fisher Jenks method
#Author: Rachel Gramlich
#Date Updated: 2023-09-14


#Table creation query goes here


#importing packages
import pandas as pd
import jenkspy
import numpy as np
from matplotlib import pyplot as plt
import jenkspy
from jenks import jenks
import seaborn as sns

#connect to bigquery
from analytics_cloud_core import Clients, ClientType
client = Clients.get_bigquery(project="projectnamegoeshere")




# Read from GBQ table and write results to dataframe
data = client.query(
"SELECT * FROM tablename WHERE visits > 0 and orders > 0"
).result().to_dataframe()

df = data.sort_values(by='visits')




#visualize dataframe
print(df)



#Plotting histogram to visualize product visits data set
hist = plt.hist(df['visits'], bins=100, align='left', color = 'blue')
plt.xlabel('visits')
plt.ylabel('products')


#Plotting histogram to visualize order count data set
hist = plt.hist(df['orders'], bins=100, align='left', color = 'blue')
plt.xlabel('orders')
plt.ylabel('products')


#creating function to find goodness of variance fit
def goodness_of_variance_fit(array, classes):
    # get the break points
    classes = jenks(array, classes)

    # do the actual classification
    classified = np.array([classify(i, classes) for i in array])

    # max value of zones
    maxz = max(classified)

    # nested list of zone indices
    zone_indices = [[idx for idx, val in enumerate(classified) if zone + 1 == val] for zone in range(maxz)]

    # sum of squared deviations from array mean
    sdam = np.sum((array - array.mean()) ** 2)

    # sorted polygon stats
    array_sort = [np.array([array[index] for index in zone]) for zone in zone_indices]

    # sum of squared deviations of class means
    sdcm = sum([np.sum((classified - classified.mean()) ** 2) for classified in array_sort])

    # goodness of variance fit
    gvf = (sdam - sdcm) / sdam

    return gvf


#find optimum number of classes
def classify(value, breaks):
    for i in range(1, len(breaks)):
        if value < breaks[i]:
            return i
    return len(breaks) - 1


#determine optimal number of clusters algorithmically
#increment nclasses until gvf .8 is achieved for each column, and print nclasses and gvf
for col in df.columns[1:3]:
    gvf = 0.0
    nclasses = 2
    while gvf < .8:
        gvf = goodness_of_variance_fit(df[col].to_numpy(), nclasses)
        nclasses += 1
    print(nclasses)
    print(gvf)


#creating chart of gvf vs number of clusters to visualize best # of clusters to choose

my_dict = {}
for col in df.columns[1:3]:
    results = []
    for i in range(2, 10):
        results.append(goodness_of_variance_fit(df[col].to_numpy(), i))
    my_dict[col] = results
plt.plot(range(2, 10), my_dict['visits'], label='visits')
plt.plot(range(2, 10), my_dict['orders'], label='orders')
plt.xlabel('Number of clusters')
plt.ylabel('Goodness of Variance Fit')
plt.legend(loc='best')
plt.show()


#determine number of clusters for visits




#finding natural breaks, once nb_class is determined (the number of breaks)
visits_jbreaks4 = jenkspy.jenks_breaks(df['visits'].to_numpy(), nb_class=4)
visits_jbreaks3 = jenkspy.jenks_breaks(df['visits'].to_numpy(), nb_class=3)
visits_jbreaks2 = jenkspy.jenks_breaks(df['visits'].to_numpy(), nb_class=2)



#printing breaks
print(visits_jbreaks4)
print(visits_jbreaks3)
print(visits_jbreaks2)


#Plotting histogram for each of jbreaks 2,3,4 for productvisits
hist = plt.hist(df['visits'], bins=100, align='left', color = 'yellow')
plt.xlabel('visits')
plt.ylabel('products')
plt.title('nclasses=3')
plt.ylim(0,100) #100 as max in order to visualize rest of chart - high product count at 0.
for b in visits_jbreaks2:
    plt.vlines(b, ymin=0, ymax = max(hist[0]), color = 'red')
#for b in visits_jbreaks3:
#    plt.vlines(b, ymin=0, ymax = max(hist[0]), color = 'green')
#for b in visits_jbreaks2:
#    plt.vlines(b, ymin=0, ymax = max(hist[0]), color = 'blue')


#determine number of clusters for orders


#finding natural breaks, once nb_class is determined (the number of breaks)
orders_jbreaks4 = jenkspy.jenks_breaks(df['orders'].to_numpy(), nb_class=4)
orders_jbreaks3 = jenkspy.jenks_breaks(df['orders'].to_numpy(), nb_class=3)
orders_jbreaks2 = jenkspy.jenks_breaks(df['orders'].to_numpy(), nb_class=2)


#df['quantilev2'] = pd.qcut(
#    df['visits'], q=3, labels=['not trending', 'average', 'trending'])

#reset df to base data, remove any added columns in testing
df=data

df['visits_jbreaks2_range'] = pd.cut(
    df['visits'],
    bins=visits_jbreaks2,
    include_lowest=True)


df['visits_jbreaks2'] = pd.cut(
    df['visits'],
    bins=visits_jbreaks2,
    labels=['not trending','trending'],
    include_lowest=True)

df['ordercount_jbreaks2_range'] = pd.cut(
    df['orders'],
    bins=orders_jbreaks2,
    include_lowest=True)

df['ordercount_jbreaks2'] = pd.cut(
    df['orders'],
    bins=orders_jbreaks2,
    labels=['not selling', 'selling'],
    include_lowest=True)

df.head()


df.groupby(['visits_jbreaks2','ordercount_jbreaks2']).describe().round(0)[['visits','orders']]






df.groupby(['visits_jbreaks2','visits_jbreaks2_range','ordercount_jbreaks2','ordercount_jbreaks2_range']).count()['product']



#printing breaks
print(orders_jbreaks4)
print(orders_jbreaks3)
print(orders_jbreaks2)


#Plotting histogram for each of jbreaks 2,3,4 for orders
hist = plt.hist(df['orders'], bins=100, align='left', color = 'yellow')
plt.xlabel('orders')
plt.ylabel('products')
plt.title('nclasses=3')
plt.ylim(0,100) #100 as max in order to visualize rest of chart - high product count at 0.
for b in orders_jbreaks3:
    plt.vlines(b, ymin=0, ymax = max(hist[0]), color = 'red')
#for b in orders_jbreaks3:
#    plt.vlines(b, ymin=0, ymax = max(hist[0]), color = 'green')
#for b in orders_jbreaks2:
#    plt.vlines(b, ymin=0, ymax = max(hist[0]), color = 'blue')
