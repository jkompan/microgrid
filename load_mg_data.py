# %%
import os
import pandas as pd
import numpy as np
import re

def load_microgrid_data(dir):
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
    filepath = os.path.join(dir, 'building_attributes_base.json')
    with open(filepath,'r') as f:
        solar = re.findall('(?<="Solar_Power_Installed\(kW\)":)\d+',f.read())
        solar = [int(s) for s in solar]
        
    # solar generation data
    filepath = os.path.join(dir, 'solar_generation_1kW.csv')
    temp = pd.read_csv(filepath)
    df['SolarGen'] = 0
    for val in solar:
        df['SolarGen'] += val*temp.iloc[:,1]/100

    # net load
    df['NetLoad'] = df['Load'] - df['SolarGen']

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

    # dummy timestamp for easier reference
    df['Timestamp'] = pd.date_range(start='2016-01-01 01:00', periods=4*365*24, freq='h')

    # move predictions for time t to observation t
    for h in [6,12,24]:    
        for id in [index for index, col in enumerate(df.columns) if str(h)+'h Prediction' in col]:
            df.iloc[h:df.shape[0],id] = df.iloc[0:df.shape[0]-h,id]
            
    # drop first 24 hours due to lack of forecasts
    df = df.iloc[24:]
    df = df.reset_index(drop=True)