from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import cryptolytic.data.historical as h
from cryptolytic.start import init

def arb():
    # get (normalized/feature engineered) data and model get model for a given trading pair
    # train test split
    # two week gap between train and test sets to check model performance (maybe not)
    # load model, prun predictiotn s
    pass

def performance(X_test, y_preds):
    """ Takes in a test dataset and a model's predictions, calculates and returns
        the profit or loss. When the model generates consecutive buy predictions, 
        anything after the first one are considered a hold and fees are not added
        for the hold trades. """
    
    fee_rate = 0.35 
    
    # creates dataframe for features and predictions
    df_preds = X_test
    df_preds['y_preds'] = y_preds
    
    # creates column with 0s for False predictions and 1s for True predictions
    df_preds['binary_y_preds'] = df_preds['y_preds'].shift(1).apply(lambda x: 1 if x == True else 0)
    
    # performance results from adding the closing difference percentage of the rows where trades were executed
    performance = ((10000 * df_preds['binary_y_preds']*df_preds['close_diff']).sum())
    
    # calculating fees and improve trading strategy
    # creates a count list for when trades were triggered
    df_preds['preds_count'] = df_preds['binary_y_preds'].cumsum()
    
    # feature that determines the instance of whether the list increased
    df_preds['increase_count'] = df_preds['preds_count'].diff(1)
    
    # feature that creates signal of when to buy(1), hold(0), or sell(-1)
    df_preds['trade_trig'] = df_preds['increase_count'].diff(1)
    
    # number of total entries(1s)
    number_of_entries = (df_preds.trade_trig.values==1).sum()
    
    # performance takes into account fees given the rate at the beginning of this function
    pct_performance = ((df_preds['binary_y_preds']*df_preds['close_diff']).sum())
    
    # calculate the percentage paid in fees
    fees_pct = number_of_entries * 2 * fee_rate/100
    
    # calculate fees in USD 
    fees = number_of_entries * 2 * fee_rate / 100 * 10000
    
    # calculate net profit in USD
    performance_net = performance - fees
    
    # calculate net profit percent
    performance_net_pct = performance_net/10000

    return pct_performance, performance, fees, performance_net, performance_net_pct

def trade_model(df):
    # load data 
    max_depth = 17
    max_features = 40

    # get data with feature engineering
    # check that the data is valid (no empty or small dataframes)
    # train test split 

    train_size = int(df.shape[0] * 0.8)
    train = df.iloc[0:train_size]
    test = df.iloc[train_size:]


    features = df.columns[0:50] # first 50 columns as features for right now
    target = 'price_increased'
    # define X, y vectors
    X_train = train[features]
    X_test = test[features]
    y_train = train[target]
    y_test = test[target]

    # Random forest classifier
    model = RandomForestClassifier(max_features=max_features, 
                           max_depth=max_depth,
                           n_estimators=100,
                           n_jobs=-1,
                           random_state=42)
    
    model.fit(X_train, y_train)
    train_score=  model.score(X_train, y_train)
    y_preds = model.predict(X_test)
    score = accuracy_score(y_test, y_preds)

    return y_preds, score

    # Get profit and loss
    # 

def test_trade_model():
    init()
    exchange_id = 'hitbtc'
    trading_pair = 'eos_usd'
    period = 300
    start = '03-01-2019'
    
    df, dataset = h.get_data(exchange_id, trading_pair, period, start, n=8000)
    preds, score = trade_model(df)

    print(score)
    print(preds)

    exchange_id = 'hitbtc'
    trading_pair = 'btc_usd'
    period = 300
    start = '03-01-2019'
    
    df, dataset = h.get_data(exchange_id, trading_pair, period, start, n=8000)
    preds, score = trade_model(df)

    print(score)
    print(preds)

