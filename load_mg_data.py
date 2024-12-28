# %%
import os
import pandas as pd
import numpy as np
import re

def load_microgrid_data(dir):
    """
    Loads and processes microgrid data from the specified directory.

    This function performs the following steps:
    1. Loads demand (load) data from CSV files starting with 'Building_'.
    2. Processes the demand data to calculate total load and individual building loads.
    3. Loads solar power installation data from a JSON file.
    4. Loads solar generation data from a CSV file and calculates total solar generation.
    5. Calculates net load by subtracting solar generation from total load.
    6. Creates lagged features and rolling statistics.
    7. Loads electricity pricing data from a CSV file and merges it with the main dataframe.

    Parameters:
    dir (str): The directory containing the microgrid data files.

    Returns:
    pd.DataFrame: A pandas DataFrame containing the processed microgrid data.
    """

    # demand data
    n = 1
    for filename in os.listdir(dir):
        if not filename.startswith('Building_'):
            continue
        filepath = os.path.join(dir, filename)
        if filename=='Building_1.csv':
            df = pd.read_csv(filepath)
            df['DayType'] = df['Day Type'].astype('int64').replace({2:'Mon',3:'Tue',4:'Wed',5:'Thu',6:'Fri',7:'Sat',8:'Holiday',1:'Sun'}).astype('category')
            df['Month'] = df['Month'].astype('category')
            df['Workday'] = df['DayType'].apply(lambda x: False if x in ['Sat','Sun','Holiday'] else True)
            df['DaylightSavings'] = df['Daylight Savings Status'].astype('int64').astype('category')
            df['Load'] = df.iloc[:,7]+df.iloc[:,8]+df.iloc[:,9]
            df[f'Load_{n}'] = df.iloc[:,7]+df.iloc[:,8]+df.iloc[:,9]
            df.drop(df.columns[2:10], axis=1, inplace=True)
        else:
            temp = pd.read_csv(filepath)
            df['Load'] += temp.iloc[:,7]+temp.iloc[:,8]+temp.iloc[:,9]
            df[f'Load_{n}'] = temp.iloc[:,7]+temp.iloc[:,8]+temp.iloc[:,9]
        n += 1

    # solar installed data
    filepath = os.path.join(dir, 'building_attributes.json')
    with open(filepath,'r') as f:
        power_installed = re.findall('(?<="Solar_Power_Installed\(kW\)":)\d+',f.read())
        power_installed = [int(s) for s in power_installed]
        
    # solar generation data
    filepath = os.path.join(dir, 'solar_generation_1kW.csv')
    temp = pd.read_csv(filepath)
    df['SolarGen'] = 0
    for val in power_installed:
        df['SolarGen'] += val*temp.iloc[:,1]/1000

    # net load
    df['NetLoad'] = df['Load'] - df['SolarGen']
    # lags
    lags = [1, 2, 3, 4, 5, 6, 22, 23, 24, 48]
    for lag in lags:
        df[f'NetLoadLag{lag}'] = df['NetLoad'].shift(lag)
    df['NetLoadMax24'] = df['NetLoad'].rolling(window=24, min_periods=1).max()
    df['NetLoadMin24'] = df['NetLoad'].rolling(window=24, min_periods=1).min()
    df['NetLoadDiff24'] = df['NetLoad'].diff(24)

    # rates
    # filepath = os.path.join(dir, 'prices.csv')
    # temp = pd.read_csv(filepath)
    # temp.drop(temp.columns[5:8],axis=1,inplace=True)
    # temp['DayType'] = temp['Day Type']
    # temp = temp.groupby(['Month','DayType','Hour'])['Electricity Pricing [$]'].mean().reset_index()
    # df = pd.merge(df, temp, on=['Month','DayType','Hour'],how='left')
    filepath = os.path.join(dir, 'prices.csv')
    temp = pd.read_csv(filepath)
    df['Price'] = temp.iloc[:,0]

    # weather data
    filepath = os.path.join(dir, 'weather_data.csv')
    temp = pd.read_csv(filepath)
    df = pd.concat([df,temp],axis=1)
    df['Radiation [W/m2]'] = df['Diffuse Solar Radiation [W/m2]'] + df['Direct Solar Radiation [W/m2]']
    df['6h Prediction Radiation [W/m2]'] = df['6h Prediction Diffuse Solar Radiation [W/m2]'] + df['6h Prediction Direct Solar Radiation [W/m2]']
    df['12h Prediction Radiation [W/m2]'] = df['12h Prediction Diffuse Solar Radiation [W/m2]'] + df['12h Prediction Direct Solar Radiation [W/m2]']
    df['24h Prediction Radiation [W/m2]'] = df['24h Prediction Diffuse Solar Radiation [W/m2]'] + df['24h Prediction Direct Solar Radiation [W/m2]']
    # temperature lags
    for lag in [1, 2, 3, 22, 23, 24]:
        df[f'TempLag{lag}'] = df['Outdoor Drybulb Temperature [C]'].shift(lag)
    df['TempMean24'] = df['Outdoor Drybulb Temperature [C]'].rolling(window=24, min_periods=1).mean()
    df['TempMean1W'] = df['Outdoor Drybulb Temperature [C]'].rolling(window=168, min_periods=21).mean()

    # dummy timestamp for easier reference
    df['Timestamp'] = pd.date_range(start='2016-01-01 01:00', periods=4*365*24, freq='h')

    # move predictions for time t to observation t
    for h in [6,12,24]:    
        for id in [index for index, col in enumerate(df.columns) if str(h)+'h Prediction' in col]:
            df.iloc[h:df.shape[0],id] = df.iloc[0:df.shape[0]-h,id]
            
    # drop first 48 hours due to missing data
    df = df.iloc[48:]
    df = df.reset_index(drop=True)