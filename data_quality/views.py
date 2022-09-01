from django.shortcuts import render
from django_pandas.io import *
from django.db import IntegrityError

from indicators.models import FactDataIndicator
import pandas as pd
import numpy as np
from fuzzywuzzy import fuzz,process
from functools import reduce

import json

from sqlalchemy import create_engine #helper for saving dataframes to db
import MySQLdb # drivers for accessing the database through sqlalchemy

from .models import (Facts_DataFrame,CategoryOptions_Validator,MeasureTypes_Validator,
    DataSource_Validator,Mutiple_MeasureTypes,DqaInvalidDatasourceRemarks,
    DqaInvalidCategoryoptionRemarks,DqaInvalidMeasuretypeRemarks,Similarity_Index,
    DqaInvalidPeriodRemarks,DqaExternalConsistencyOutliersRemarks,
    DqaInternalConsistencyOutliersRemarks,DqaValueTypesConsistencyRemarks
    )


def check_data_quality(request):
    facts_df = None # initialize the facts dataframe with a null value
    groups = list(request.user.groups.values_list('user', flat=True))
    user = request.user.id  
    location = request.user.location.name
    language = request.LANGUAGE_CODE 
    qs = Facts_DataFrame.objects.all().order_by('indicator_name')
    
    if request.user.is_superuser:
        qs=qs # show all records if logged in as super user
    elif user in groups: # return records on if the user belongs to the group
        qs=qs.filter(location=location)
    else: # return records belonging to logged in user
        qs=qs.filter(user=user) 

    if len(qs) >0: # create dataframe based on logged in user
        facts_df = qs.to_dataframe(['fact_id', 'indicator_name', 'location',
                'categoryoption','datasource','measure_type',
                'value','period'],index='fact_id')



        data=facts_df.rename({'fact_id':'fact_id', 'indicator_name':'Indicator Name', 
            'location':'Country','categoryoption':'CategoryOption','datasource':'DataSource',
            'measure_type':'measure type','value':'Value','period':'Year'},axis=1)



        data = data[data.Country.notna()] 
        Countries = data['Country'].unique()

        # import pdb; pdb.set_trace()     


        # -----------------------------------Start Save Data Validation DataFrames---------------------------------------------------------
        # Create data source dataframe and save it into the database into measure types model 
        MesureTypeValid = pd.read_csv('Datasets/Mesuretype.csv', encoding='iso-8859-1')
        
        MesureTypeValid.rename({'IndicatorId':'afrocode','Indicator Name':'indicator_name', 
                'measurementmethod':'measure_type','measuremethod_id':'measuremethod_id'},
                axis=1, inplace=True)    
        measuretypes = json.loads(MesureTypeValid.to_json(
            orient='records', index=True))  # converts json to dict
        # Use try..except block to loop through and save measure objects into the database
        try:
            for record in measuretypes:    
                measuretype = MeasureTypes_Validator.objects.update_or_create(
                    afrocode=record['afrocode'],
                    indicator_name=record['indicator_name'],
                    measure_type=record['measure_type'],
                    measuremethod_id=record['measuremethod_id'],
                )
        except:
            pass


        # Create data source dataframe and save it into the database into the datasource model
        DataSourceValid = pd.read_csv('Datasets/Datasource.csv', encoding='iso-8859-1')  
        DataSourceValid.rename(
            {'IndicatorId':'afrocode','Indicator Name':'indicator_name', 
                'DataSource':'datasource','DatasourceId':'datasource_id'},
                axis=1, inplace=True)   
        datasources = json.loads(DataSourceValid.to_json(
            orient='records', index=True))  # converts json to dict

        # Use try..except block to loop through and save measure objects into the database
        try:
            for record in datasources:
                datasource = DataSource_Validator.objects.update_or_create(
                    afrocode=record['afrocode'],
                    indicator_name=record['indicator_name'],
                    datasource=record['datasource'],
                    datasource_id=record['datasource_id'],
                )
        except:
            pass
        
        # Create data source dataframe and save it into the database into the datasource model
        CategoryOptionValid = pd.read_csv('Datasets/Categoryoption.csv', encoding='iso-8859-1')
        CategoryOptionValid.rename({'IndicatorId':'afrocode','Indicator Name':'indicator_name', 
                'DataSource':'datasource','DatasourceId':'datasource_id','Category':'categoryoption',
                'CategoryId':'categoryoption_id'},axis=1, inplace=True)   

        categoryoptions = json.loads(CategoryOptionValid.to_json(
            orient='records', index=True))  # convert to records
        try:    
            for record in categoryoptions:
                categoryoption = CategoryOptions_Validator.objects.update_or_create(
                    afrocode=record['afrocode'],
                    indicator_name=record['indicator_name'],
                    categoryoption=record['categoryoption'],
                    categoryoption_id=record['categoryoption_id'],
                )
        except:
            pass
        # ----------------------------------End Data Validation DataFrames---------------------------------------------------------


        # -----------------------------------Misscellanious algorithm - Count Data Source and measure Type For Each Indicators-----
        DataSourceNumber = data.groupby(['Country', 'Indicator Name'], as_index=False).agg({"DataSource": "nunique"})
        MultipleDataSources = DataSourceNumber[DataSourceNumber.DataSource>1] # indicator with multiple sources
        
    
        # Count each country indicators with more than one measure type
        MesureTypeByIndicatorCounts = data.groupby(['Country', 'Indicator Name'], as_index=False).agg(
            {"measure type": "nunique"})
        MultipleMesureTypeIndicator = MesureTypeByIndicatorCounts[
            MesureTypeByIndicatorCounts['measure type']>1]
        MultipleMesureTypeIndicator=MultipleMesureTypeIndicator.rename({'Indicator Name':'indicator_name',
            'Country':'location','measure type':'count',},axis=1)  
                 
        # Insert comments and save indicators with more than one measure type (Didier's data 1)
        for index, row in MultipleMesureTypeIndicator.iterrows():
            data.loc[(data['Country'] == row['location']) & (
                data['Indicator Name'] == row[
                    'indicator_name']),'Check_Mesure_Type'] = "Indicator with multiple mesure types"                
        multimeasures_df = data[data.Check_Mesure_Type.str.len() > 0] # Didier's data1
        
        multi_measures_df=multimeasures_df.rename({'Indicator Name':'indicator_name',
            'Country':'location','CategoryOption':'categoryoption',
            'DataSource':'datasource','measure type':'measure_type',
            'Year':'period','Value':'value','Year':'period',
            'Check_Mesure_Type':'measures_remarks'},axis=1)       

        # Count each country indicators with more than one measure type per data source
        NumberMesureTypeByIndicatorPerDS = data.groupby(
            ['Country', 'Indicator Name', 'DataSource'], as_index=False).agg({"measure type": "nunique"})
        MultipleMesureTypeIndicatorPerDS = NumberMesureTypeByIndicatorPerDS[
            NumberMesureTypeByIndicatorPerDS['measure type']>1]

        for index, row in MultipleMesureTypeIndicatorPerDS.iterrows():
            data.loc[(data['Country'] == row['Country']) & (
                data['Indicator Name'] == row['Indicator Name']) & (
                    data['DataSource'] == row[
                        'DataSource']),'Check_Mesure_Type'] = "Multiple mesure type for this data source "
        multi_source_measures_df = data[data.Check_Mesure_Type.str.len() > 0] # Didier's data2

        multi_source_measures_df=multi_source_measures_df.rename(
            {'Indicator Name':'indicator_name','Country':'location',
            'CategoryOption':'categoryoption','DataSource':'datasource',
            'measure type':'measure_type','Year':'period','Value':'value',
            'Year':'period','Check_Mesure_Type':'remarks'},axis=1)    

        # Concatenate the two frames using columns (axis=1) and save on the database
        measures_checker_df = pd.concat((multi_measures_df, multi_source_measures_df), axis = 1)
        data.drop('Check_Mesure_Type', axis=1, inplace=True) # remove remarks from the dataframe
        # Use drop_duplicates().T to remove duplicate columns from the dataframe
        multimeasures_json = measures_checker_df.loc[:,~measures_checker_df.T.duplicated(
            keep='last')]
        # Create a json array and convert it into a python dictionary for storage      
        multimeasures_checker = json.loads(multimeasures_json.to_json(
            orient='records',index=True,indent=4))  # converts json to dict
        try:    
            for record in multimeasures_checker:
                # import pdb; pdb.set_trace()     
                multimeasures = Mutiple_MeasureTypes.objects.update_or_create(
                    indicator_name=record['indicator_name'],
                    location=record['location'],
                    categoryoption=record['categoryoption'],
                    datasource=record['datasource'],
                    measure_type=record['measure_type'],
                    value=record['value'],
                    period=record['period'],
                    counts=record['counts'],
                    remarks=record['remarks'],                   
                )
        except:
            pass        


    # -------------------------------Import algorithm 1 - indicators with wrong measure types--------------------------
        valid_datasources_qs = DataSource_Validator.objects.all().order_by('afrocode')
        bad_datasource =None
        if len(qs) >0:
            DataSourceValid = valid_datasources_qs.to_dataframe(['id', 'afrocode', 'indicator_name',
                'datasource','datasource_id'],index='id')
            DataSourceValid.rename({'indicator_name':'Indicator Name',
                'datasource':'DataSource'},axis=1, inplace=True)
            UniqueIndicatorV = DataSourceValid['Indicator Name'].unique().tolist()
            
            dataWDS = pd.DataFrame(columns=data.columns.tolist()) # create an emplty list of columns from facts dataset
            for indicator in UniqueIndicatorV: # iterate through the data source list of indicators 
                ValidDataSource = DataSourceValid[
                    DataSourceValid['Indicator Name']==indicator]['DataSource'] # get all datasources for the indicator                
                ValidDataSource = ValidDataSource.unique().tolist() # create a list of valid sources [country, who/gho,nis]
                ActualDataSource = data[data['Indicator Name']==indicator]['DataSource'] # get all data sources from dataset
                ActualDataSource = ActualDataSource.unique().tolist()
                WDS = list(set(ActualDataSource) - set(ValidDataSource))
                if(len(WDS)!=0): # check whether the set diffrence is zero
                    for ds in WDS:
                        IWWDS = data[(data['Indicator Name']==indicator) & (
                            data['DataSource']==ds)] # indicator with wrong data source
                        dataWDS = pd.concat((dataWDS,IWWDS), axis = 0,ignore_index = True) # append rows (axis=0) into the empty dataframe
            dataWDS.loc[:,'Check_Data_Source'] = 'This data source is not applicable to this indicator'
            bad_datasource = dataWDS # Didier's data3: create dataframe for wrong data sources
            
            if not bad_datasource.empty: # use a.empty instead of boolean to check whether df is empty
                bad_datasource_df=bad_datasource.rename(
                    {'Indicator Name':'indicator_name','Country':'location',
                    'CategoryOption':'categoryoption','DataSource':'datasource',
                    'measure type':'measure_type','Value':'value','Year':'period',
                    'Check_Data_Source':'check_data_source'},axis=1)   
            
                datasource_checker = json.loads(bad_datasource_df.to_json(
                    orient='records',index=True,indent=4))  # converts json to dict
                try:    
                    for record in datasource_checker:
                        # import pdb; pdb.set_trace()     
                        datasources = DqaInvalidDatasourceRemarks.objects.update_or_create(
                            indicator_name=record['indicator_name'],
                            location=record['location'],
                            categoryoption=record['categoryoption'],
                            datasource=record['datasource'],
                            measure_type=record['measure_type'],
                            value=record['value'],
                            period=record['period'],
                            check_data_source=record['check_data_source'],                   
                        )
                except:
                    pass   


        # -------------------------------Import algorithm 2 - indicators with wrong category options--------------------------
        valid_categoryoptions_qs = CategoryOptions_Validator.objects.all().order_by('afrocode')
        categoryoption_df = None
        if len(qs) >0:
            CategoryOptionValid = valid_categoryoptions_qs.to_dataframe(['id', 'afrocode', 'indicator_name',
                'categoryoption','categoryoption_id'],index='id')
            CategoryOptionValid.rename({'indicator_name':'Indicator Name','categoryoption':'Category'},
                axis=1, inplace=True)
            UniqueIndicatorV = DataSourceValid['Indicator Name'].unique().tolist()
            
            dataWCO = pd.DataFrame(columns=data.columns.tolist())
            for indicator in UniqueIndicatorV:               
                ValidCO = CategoryOptionValid[CategoryOptionValid['Indicator Name']==indicator]['Category'] # this is ok
                ValidCO = ValidCO.unique().tolist() # return ['Male', 'Female', 'Both sexes (male and female)']
                ActualCO = data[data['Indicator Name']==indicator]['CategoryOption'] # get related categoryoption from dataset for this indicator
                ActualCO = ActualCO.unique().tolist()
                WCO = list(set(ActualCO) - set(ValidCO))
                if(len(WCO)!=0):
                    for co in WCO:
                        IWWCO = data[(data['Indicator Name']==indicator) & (data['CategoryOption']==co)]
                        dataWCO = pd.concat((dataWCO,IWWCO), axis = 0,ignore_index = True) # append rows (axis=0) into the empty dataframe
                        dataWCO.loc[:,'Check_Category_Option'] = 'This category option is not applicable to this indicator'            
            categoryoption_df = dataWCO # Didier's data4: Create dataframe with check measure type remarks column
        
            if not categoryoption_df.empty: # check whether the dataframe is empty
                bad_categoryoption_df=categoryoption_df.rename(
                    {'Indicator Name':'indicator_name','Country':'location',
                    'CategoryOption':'categoryoption','DataSource':'datasource',
                    'measure type':'measure_type','Value':'value','Year':'period',
                    'Check_Category_Option':'check_category_option'},axis=1)   
                
                categoryoption_checker = json.loads(bad_categoryoption_df.to_json(
                    orient='records',index=True,indent=4))  # converts json to dict        
                try:    
                    for record in categoryoption_checker:
                        categoryoptions = DqaInvalidCategoryoptionRemarks.objects.update_or_create(
                            indicator_name=record['indicator_name'],
                            location=record['location'],
                            categoryoption=record['categoryoption'],
                            datasource=record['datasource'],
                            measure_type=record['measure_type'],
                            value=record['value'],
                            period=record['period'],
                            check_category_option=record['check_category_option'],                   
                        )
                except:
                    pass   
            
        # -------------------------------Import algorithm 3 - indicators with wrong measure types--------------------------
        valid_measures_qs = MeasureTypes_Validator.objects.all().order_by('afrocode')
        if len(qs) >0:
            MesureTypeValid = valid_measures_qs.to_dataframe(['id', 'afrocode', 'indicator_name',
                'measure_type','measuremethod_id'],index='id')
            MesureTypeValid.rename({'indicator_name':'Indicator Name',
            'measure_type':'measure type'},axis=1, inplace=True)

            UniqueIndicatorV = MesureTypeValid['Indicator Name'].unique().tolist()
            dataWMT = pd.DataFrame(columns=data.columns.tolist())
            for indicator in UniqueIndicatorV:
                ValidMT = MesureTypeValid[MesureTypeValid['Indicator Name']==indicator]['measure type'] # get valid measure types
                ValidMT = ValidMT.unique().tolist()
                ActualMT = data[data['Indicator Name']==indicator]['measure type']
                ActualMT = ActualMT.unique().tolist()
                WMT = list(set(ActualMT) - set(ValidMT))
                if(len(WMT)!=0):
                    for mt in WMT:
                        IWWMT = data[(data['Indicator Name']==indicator) & (data['measure type']==mt)]
                        dataWMT = pd.concat((dataWMT,IWWMT), axis = 0,ignore_index = True) # append rows (axis=0) into the empty dataframe
                        dataWMT.loc[:,'Check_Mesure_Type'] = 'This mesure type is not applicable to this indicator'
            measuretypes_df = dataWMT # Didier's data5 Create dataframe with check measure type remarks column
            
            if not measuretypes_df.empty: # check whether the dataframe is empty
                bad_measuretype_df=measuretypes_df.rename(
                    {'Indicator Name':'indicator_name','Country':'location',
                    'CategoryOption':'categoryoption','DataSource':'datasource',
                    'measure type':'measure_type','Value':'value','Year':'period',
                    'Check_Mesure_Type':'check_mesure_type'},axis=1)     
                measuretype_checker = json.loads(bad_measuretype_df.to_json(
                    orient='records',index=True,indent=4))  # converts json to dict
                try:    
                    for record in measuretype_checker:
                        measuretypes = DqaInvalidMeasuretypeRemarks.objects.update_or_create(
                            indicator_name=record['indicator_name'],
                            location=record['location'],
                            categoryoption=record['categoryoption'],
                            datasource=record['datasource'],
                            measure_type=record['measure_type'],
                            value=record['value'],
                            period=record['period'],
                            check_mesure_type=record['check_mesure_type'],                   
                        )
                except:
                    pass   


        # -------------------------------------Start of comparing indicators for similarity score----------------------------        
        UniqueInd = data['Indicator Name'].unique()
        _list_comparison_fullname = []
        _list_entry_fullname = []
        _list_entry_score = []
        for i_dataframe in range(len(UniqueInd)-1):
            comparison_fullname = UniqueInd[i_dataframe]
            for entry_fullname, entry_score in process.extract(comparison_fullname, 
                # NB: fuzz.token_sort_ratio ratio gives higher scores compared to ratio fuzz.ratio
                UniqueInd[i_dataframe+1::],scorer=fuzz.token_sort_ratio): 
                if entry_score >=60:
                    _list_comparison_fullname.append(comparison_fullname) #append* inserts an element to the list 
                    _list_entry_fullname.append(entry_fullname)
                    _list_entry_score.append(entry_score)
                
        CheckIndicatorNameForSimilarities = pd.DataFrame(
            {'IndicatorName':_list_entry_fullname,
            'SimilarIndicator':_list_comparison_fullname,
            'Score':_list_entry_score})   
        Check_similarities=CheckIndicatorNameForSimilarities.rename(
            {'IndicatorName':'source_indicator','SimilarIndicator':'similar_indicator',
            'Score':'score'},axis=1)            
        Check_similarities.sort_values(by=['score'],inplace=True,ascending=False)   
        similarities_checker = json.loads(Check_similarities.to_json(
            orient='records',index=True,indent=4))  # converts json to dict
        try:    
            for record in similarities_checker:
                similarities = Similarity_Index.objects.update_or_create(
                    source_indicator=record['source_indicator'],
                    similar_indicator=record['similar_indicator'],
                    score=record['score'],                   
                )
        except:
            pass    

        # -------------------------------------End of comparing indicators for similarity score----------------------------             

        # -------------------------------Start of miscellanious algorithms - Year verification -----------------------------------
        dataWithSelectedColumns = data[['Country', 'Indicator Name', 'DataSource', 'Year']]

        dataWithSelectedColumns['CYear'] = dataWithSelectedColumns['Year'].apply(len) #count characters in year string
 

        NumberYearTypeIndicator = dataWithSelectedColumns.groupby(
            ['Country', 'Indicator Name', 'DataSource'], as_index=False).agg({"CYear": "nunique"})
        MultipleYearTypeIndicator = NumberYearTypeIndicator[NumberYearTypeIndicator['CYear']>1]
        
        if not MultipleYearTypeIndicator.empty: # check whether the dataframe is empty
            for index, row in MultipleYearTypeIndicator.iterrows():
                data.loc[(data['Country'] == row['Country']) & (
                    data['Indicator Name'] == row['Indicator Name']) & (
                        data['DataSource'] == row[
                            'DataSource']),'Check_Year'] ="This indicator has range and single year "
            periods_df = data[data.Check_Year.str.len() > 0] # Didier's data6
            bad_periods_df=periods_df.rename(
                {'Indicator Name':'indicator_name','Country':'location',
                'CategoryOption':'categoryoption','DataSource':'datasource',
                'measure type':'measure_type','Value':'value','Year':'period',
                'Check_Year':'check_year'},axis=1)     
            
            data.drop('Check_Year', axis=1, inplace=True) # remove period remarks from the facts dataframe
            
            periods_checker = json.loads(bad_periods_df.to_json(
                orient='records',index=True,indent=4))  # converts json to dict
            try:    
                for record in periods_checker:
                    periods = DqaInvalidPeriodRemarks.objects.update_or_create(
                        indicator_name=record['indicator_name'],
                        location=record['location'],
                        categoryoption=record['categoryoption'],
                        datasource=record['datasource'],
                        measure_type=record['measure_type'],
                        value=record['value'],
                        period=record['period'],
                        check_year=record['check_year'],                   
                    )
            except:
                pass   
        

        # --------------Start of consistency inpection algorithms. To be replace with corrected from Didier and Berence---
        dataCountMT = data[data['measure type'] == 'Count (Numeric Integer)']
        dataCountMT['Value'] = pd.to_numeric(dataCountMT['Value'], errors='coerce')
        externaloutliers_df = None
        
        # External consistency : By Indicator per categoryoption (Considering all category options )
        CountriesCMT = dataCountMT['Country'].unique().tolist()
        ExOutliersCMT = pd.DataFrame(columns=dataCountMT.columns.tolist())
    
        for country in CountriesCMT:
            dataC = dataCountMT[dataCountMT['Country'] == country]
            CIndicatorsCMT = dataC['Indicator Name'].unique().tolist()
            for indicator in CIndicatorsCMT:
                CdataR = dataC[dataC['Indicator Name'] == indicator]
                CatOptCMT = CdataR['CategoryOption'].unique().tolist()
                for catopt in CatOptCMT:
                    dataCOpt = CdataR[CdataR['CategoryOption'] == catopt]
                    MeanVal = np.mean(dataCOpt['Value'])
                    SDVal = np.std(dataCOpt['Value']) 
                    dataCOpt = dataCOpt[( # replaced append() with concat() function due to depricated append
                        dataCOpt.Value > MeanVal + 3*SDVal) | (dataCOpt.Value < MeanVal - 3*SDVal)]
                    if len(dataCOpt)!=0: #improved Didier's algorithm to check for empty list
                        ExOutliersCMT =  pd.concat((
                            ExOutliersCMT,dataCOpt),axis = 0,ignore_index = True)
                        ExOutliersCMT.loc[:,'Check_value'] = 'External consistency violation: \
                            This value seems to be an outlier'
        externaloutliers_df = ExOutliersCMT #Didier's data9

        if not externaloutliers_df.empty: # check whether the dataframe is empty
            external_outliers_df=externaloutliers_df.rename(
                {'Indicator Name':'indicator_name','Country':'location','CategoryOption':'categoryoption',
                'DataSource':'datasource','measure type':'measure_type','Value':'value','Year':'period',
                'Check_value':'external_consistency'},
            axis=1)   
            extraconsistency_checker = json.loads(external_outliers_df.to_json(
                orient='records',index=True,indent=4))  # converts json to dict
            try:    
                for record in extraconsistency_checker:
                    extraconsistencies = DqaExternalConsistencyOutliersRemarks.objects.update_or_create(
                        indicator_name=record['indicator_name'],
                        location=record['location'],
                        categoryoption=record['categoryoption'],
                        datasource=record['datasource'],
                        measure_type=record['measure_type'],
                        value=record['value'],
                        period=record['period'],
                        external_consistency=record['external_consistency'],                   
                    )
            except:
                pass  

        # Internal consistency : By Indicator per categoryoption (Considering all data sources )
        CountriesCMT = dataCountMT['Country'].unique().tolist()
        InOutliersCMT = pd.DataFrame(columns=dataCountMT.columns.tolist())
        internaloutliers_df = None

        for country in CountriesCMT:
            dataC = dataCountMT[dataCountMT['Country'] == country]
            CIndicatorsCMT = dataC['Indicator Name'].unique().tolist()
            for indicator in CIndicatorsCMT:
                CdataR = dataC[dataC['Indicator Name'] == indicator]
                CatOptCMT = CdataR['CategoryOption'].unique().tolist()
                for catopt in CatOptCMT:
                    dataCOpt = CdataR[CdataR['CategoryOption'] == catopt]
                    dataSourceCMT = dataCOpt['DataSource'].unique().tolist()
                    for ds in dataSourceCMT:
                        dataDS = dataCOpt[dataCOpt['DataSource'] == ds]
                        MeanVal = np.mean(dataDS['Value'])
                        SDVal = np.std(dataDS['Value'])   
                        dataDS = dataDS[( # replaced append() with concat()
                            dataDS.Value > MeanVal + 3*SDVal) | (dataDS.Value < MeanVal - 3*SDVal)]
                        if len(dataDS)!=0: #improved Didier's algorithm to check for empty list
                            InOutliersCMT =  pd.concat((InOutliersCMT,dataDS),axis = 0,ignore_index = True)
                            InOutliersCMT.loc[:,'Check_value'] = 'Internal consistency violation: \
                                This value seems to be an outlier'
        internaloutliers_df = InOutliersCMT #Didier's data10

        if not internaloutliers_df.empty: # check whether the dataframe is empty
            internal_outliers_df=internaloutliers_df.rename(
                {'Indicator Name':'indicator_name','Country':'location',
                'CategoryOption':'categoryoption','DataSource':'datasource',
                'measure type':'measure_type','Value':'value','Year':'period',
                'Check_value':'internal_consistency'},axis=1)   

            intraconsistency_checker = json.loads(internal_outliers_df.to_json(
                orient='records',index=True,indent=4))  # converts json to dict

            try:    
                for record in intraconsistency_checker:
                    intraconsistencies = DqaInternalConsistencyOutliersRemarks.objects.update_or_create(
                        indicator_name=record['indicator_name'],
                        location=record['location'],
                        categoryoption=record['categoryoption'],
                        datasource=record['datasource'],
                        measure_type=record['measure_type'],
                        value=record['value'],
                        period=record['period'],
                        internal_consistency=record['internal_consistency'],                   
                    )
            except:
                pass  
        # --------------End of consistency inspection algorithms. To be replace with corrected from Didier and Berence---


        # -----------Miscellaneous algorithm for checking Consistancies per mesure type: Count(numeric Integer) ---------- 
        # Checking consistancies per mesure type: Not numeric Value
        CountOverAllChecking = dataCountMT[dataCountMT['Value'].isna()]
        
        if not CountOverAllChecking.empty: # check whether the dataframe is empty
            CountOverAllChecking.loc[:,'Check_value'] = 'This value does not suit with its mesure type'
            integervalue_df = CountOverAllChecking # Didier's data7 Total alcohol per capita (age 15+ years) consu... WHO / GHO  NaN

            # Return values with not null floating point
            dataCountMT_WNNFP = dataCountMT[dataCountMT['Value'].apply(lambda x: x % 1 )>0.001]
            dataCountMT_WNNFP.loc[:,'Check_value'] = 'This mesure type does not allow floating point'
            floatvalue_df = dataCountMT_WNNFP #Didier's data8 
                    
            combinedvalue_checker = pd.concat([integervalue_df,floatvalue_df],axis=0) # append rows (axis=0)
            combinedvalue_checker.rename({'Indicator Name':'indicator_name',
                'Country':'location','CategoryOption':'categoryoption',
                'DataSource':'datasource','measure type':'measure_type',
                'Value':'value','Year':'period','Check_value':'check_value'},
                axis=1, inplace=True) 

            valuetypes_checker = json.loads(combinedvalue_checker.to_json(
                    orient='records',index=True,indent=4))  # converts json to dict
            try:    
                for record in valuetypes_checker:
                    valuetypes = DqaValueTypesConsistencyRemarks.objects.update_or_create(
                        indicator_name=record['indicator_name'],
                        location=record['location'],
                        categoryoption=record['categoryoption'],
                        datasource=record['datasource'],
                        measure_type=record['measure_type'],
                        value=record['value'],
                        period=record['period'],
                        check_value=record['check_value'],                   
                    )
            except:
                pass 

    else: 
        print('No data') 
        
# -----------------End of data validation algorithms derived from Didier's pandas code---------------------------------
    success ="Data validation reports created and saved into the Database"
    context = {              
        'success':success,
    }
    return render(request,'data_quality/home.html',context)