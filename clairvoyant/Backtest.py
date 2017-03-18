import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from matplotlib.colors     import ListedColormap
from numpy                 import meshgrid, arange, c_
from sklearn.svm           import SVC
from sklearn.preprocessing import StandardScaler
from pandas                import read_csv, to_datetime
from numpy                 import vstack, hstack
from csv                   import DictWriter
from dateutil.parser       import parse
from pytz                  import timezone
from clairvoyant.utils     import (DateIndex, FindConditions, PercentChange,
                                   Predict)

class Backtest:

    def __init__(self, variables, trainStart, trainEnd, testStart, testEnd,
                 buyThreshold = 0.65, sellThreshold = 0.65, C = 1, gamma = 10,
                 continuedTraining = False, tz=timezone('UTC')):

        # Conditions
        self.variables          = variables
        self.trainStart         = tz.localize(to_datetime(trainStart))
        self.trainEnd           = tz.localize(to_datetime(trainEnd))
        self.testStart          = tz.localize(to_datetime(testStart))
        self.testEnd            = tz.localize(to_datetime(testEnd))
        self.buyThreshold       = buyThreshold
        self.sellThreshold      = sellThreshold
        self.C                  = C
        self.gamma              = gamma
        self.continuedTraining  = continuedTraining

        # Stats
        self.stocks             = []
        self.dates              = []
        self.totalBuys          = 0
        self.correctBuys        = 0
        self.totalSells         = 0
        self.correctSells       = 0

        # Visualize
        self.XX                 = None
        self.yy                 = None
        self.model              = None

    def runModel(self, data):
        stock = self.stocks[len(self.stocks)-1]

        trainStart = DateIndex(data, self.trainStart, False, stock)
        trainEnd   = DateIndex(data, self.trainEnd, True, stock)
        testStart  = DateIndex(data, self.testStart, False, stock)
        testEnd    = DateIndex(data, self.testEnd, True, stock)

        self.dates.append([data['Date'][trainStart].strftime('%m/%d/%Y'),
                           data['Date'][trainEnd].strftime('%m/%d/%Y'),
                           data['Date'][testStart].strftime('%m/%d/%Y'),
                           data['Date'][testEnd].strftime('%m/%d/%Y')])

        # ====================== #
        #    Initial Training    #
        # ====================== #

        X, y = [], []
        for i in range(trainStart, trainEnd+1):             # Training period

            Xs = []
            for var in self.variables:                      # Handles n variables
                Xs.append(FindConditions(data, i, var))     # Find conditions for Period 1
            X.append(Xs)

            y1 = PercentChange(data, i+1)                   # Find the stock price movement for Period 2
            if y1 > 0: y.append(1)                          # If it went up, classify as 1
            else:      y.append(0)                          # If it went down, classify as 0

        XX = vstack(X)                                      # Convert to numpy array
        yy = hstack(y)                                      # Convert to numpy array

        model = SVC(C=self.C, gamma=self.gamma, probability=True)
        model.fit(XX, yy)

        # ====================== #
        #         Testing        #
        # ====================== #

        testPeriod = testStart
        while (testPeriod < testEnd):

            # ==================================== #
            #  Period 1 @ 8:00 PM | Markets closed #
            #  Make prediction for Period 2        #
            #  Update Buy/Sell count (or neither)  #
            # ==================================== #

            Xs = []
            for var in self.variables:
                Xs.append(FindConditions(data, testPeriod, var))

            neg, pos = Predict(model, Xs)

            if   pos >= self.buyThreshold:  prediction =  1      # If positive confidence >= buyThreshold, predict buy
            elif neg >= self.sellThreshold: prediction = -1      # If negative confidence >= sellThreshold, predict sell
            else: prediction = 0

            if prediction == 1:
                self.totalBuys += 1

            elif prediction == -1:
                self.totalSells += 1

            testPeriod += 1

            # ==================================== #
            #  Period 2 @ 4:30 PM | Markets closed #
            #  Analyze results from Period 2       #
            #  Record if prediction was correct    #
            # ==================================== #

            nextPeriodPerformance = PercentChange(data, testPeriod)

            # Case 1: Prediction is positive (buy), next Period performance is positive
            if prediction == 1 and nextPeriodPerformance > 0:
                self.correctBuys += 1

            # Case 2: Prediction is positive (buy), next Period performance is negative
            elif prediction == 1 and nextPeriodPerformance <= 0: pass

            # Case 3: Prediction is negative (sell), next Period performance is negative
            elif prediction == -1 and nextPeriodPerformance < 0:
                self.correctSells += 1

            # Case 4: Prediction is negative (sell), next Period performance is positive
            elif prediction == -1 and nextPeriodPerformance >= 0: pass

            # Case 5: No confident prediction

            # ====================== #
            #     Update Model       #
            #     if specified       #
            # ====================== #

            if self.continuedTraining == True:

                X.append(Xs)

                if nextPeriodPerformance > 0: y.append(1)
                else:                      y.append(0)

                XX = vstack(X)
                yy = hstack(y)
                model.fit(XX, yy)

        # Save for vizualization purposes
        self.XX    = XX
        self.yy    = yy
        self.model = model

    def buyStats(self):
        try: return round((float(self.correctBuys)/self.totalBuys)*100,2)
        except ZeroDivisionError: return float(0)

    def sellStats(self):
        try: return round((float(self.correctSells)/self.totalSells)*100,2)
        except ZeroDivisionError: return float(0)

    def displayConditions(self):
        bld, gre, red, end = '\033[1m', '\033[92m', '\033[91m', '\033[0m'

        print(bld+"Conditions"+end)
        i = 1
        for var in self.variables:
            print(("X%s: " % i)+var)
            i += 1

        print("Buy Threshold: "  + str(self.buyThreshold*100) + "%")
        print("Sell Threshold: " + str(self.sellThreshold*100) + "%")
        print("C: " + str(self.C))
        print("gamma: " + str(self.gamma))
        print("Continued Training: "+str(self.continuedTraining))

    def displayStats(self):
        bld, gre, red, end = '\033[1m', '\033[92m', '\033[91m', '\033[0m'

        if len(self.dates) == 0:
            print("Error: Please run model before displaying stats")
            return

        print(bld+"Stats"+end)
        print("Stock(s):")
        i = 0
        for stock in self.stocks:
            print(stock+' |',
                  "Training: "+self.dates[i][0]+'-'+self.dates[i][1],
                  "Testing: "+self.dates[i][2]+'-'+self.dates[i][3])
            i += 1

        print("\nTotal Buys: " + str(self.totalBuys))
        prnt = None
        if   self.buyStats() > 50:
            prnt = gre+str(self.buyStats())+"%"+end
        elif self.buyStats() < 50:
            prnt = red+str(self.buyStats())+"%"+end
        else:
            prnt = str(self.buyStats())+"%"
        print("Buy Accuracy:", prnt)

        print("Total Sells: "   + str(self.totalSells))

        if   self.sellStats() > 50:
            prnt = gre+str(self.sellStats())+"%"+end
        elif self.sellStats() < 50:
            prnt = red+str(self.sellStats())+"%"+end
        else:
            prnt = str(self.sellStats())+"%"
        print("Sell Accuracy:", prnt)

    def visualizeModel(self, width = 5, height = 5, stepsize = 0.02):

        if len(self.variables) != 2:
            print("Error: Plotting is restricted to 2 dimensions")
            return
        if (self.XX is None or self.yy is None or self.model is None):
            print("Error: Please run model before visualizing")
            return

        X, y = self.XX, self.yy                                   # Retrieve previous XX and yy
        X = StandardScaler().fit_transform(X)                     # Normalize X values
        self.model.fit(X, y)                                      # Refit model
        x_min, x_max = X[:, 0].min() - 0.5, X[:, 0].max() + 0.5
        y_min, y_max = X[:, 1].min() - 0.5, X[:, 1].max() + 0.5
        xx, yy = meshgrid(arange(x_min, x_max, stepsize), arange(y_min, y_max, stepsize))

        plt.figure(figsize=(width, height))                       # Figure size in inches
        cm = plt.cm.RdBu                                          # Red/Blue gradients
        RedBlue = ListedColormap(['#FF312E', '#6E8894'])          # Red = 0 (Negative) / Blue = 1 (Positve)
        Axes = plt.subplot(1,1,1)                                 # Creating 1 plot
        Z = self.model.decision_function(c_[xx.ravel(), yy.ravel()])
        Z = Z.reshape(xx.shape)

        stock = self.stocks[len(self.stocks)-1]                   # Find most previous stock
        Axes.set_title(stock)                                     # Set title
        Axes.contourf(xx, yy, Z, cmap=cm, alpha=0.75)             # Contour shading
        Axes.scatter(X[:, 0], X[:, 1], c=y, cmap=RedBlue)         # Plot data points
        Axes.set_xlim(xx.min(), xx.max())                         # Limit x axis
        Axes.set_ylim(yy.min(), yy.max())                         # Limit y axis
        plt.savefig(stock+".png")                                 # Save figure
