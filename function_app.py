import azure.functions as func
import logging
import pandas as pd
from io import BytesIO
from services.blob_service import BlobService
from operations.execution import Execution
import itertools
import os
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="http_trigger_zonal")
async def http_trigger_zonal(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    query=f"""resources 
    | where type == 'microsoft.compute/virtualmachines' 
    | where tags['comment'] != '' 
    | where resourceGroup startswith 'hec' 
    | extend LandscapeID = toupper(substring(resourceGroup,0,5)) 
    | extend CustomerID = toupper(substring(resourceGroup,6,3)) 
    | extend SID = tostring(split(tags['comment'], ' ')[1]) 
    | where strlen(SID) == 3 
    | where SID!= 'for' 
    | where tags['comment'] contains ' CI '  or tags['comment'] contains 'AI' or tags['comment'] contains ' DB ' 
    | extend nic_id= tostring(properties['networkProfile']['networkInterfaces'][0]['id']) 
    //| where SID == "HEA" and CustomerID == "NEE" or SID == "N3D" and CustomerID == "NEE" or SID == "SMD" and CustomerID == "CSD" or SID == "E9E" and CustomerID == "NEE" 
    //| where SID == "N3D" and CustomerID == "NEE"
    | project id,resourceGroup, name,CustomerID,SID,tags['comment'],LandscapeID,appid=case(tags['comment'] contains 'CI','CI',tags['comment'] contains 'DB','DB','AI'),SIDCID=strcat(SID,CustomerID),zones,tenantId"""
    

    ## Fetch and Dump the blob
    obj=BlobService(storageaccount_endpoint=os.getenv("Storageaccount_endpoint"),conn_str=os.getenv('conn_str'))
    result=await obj.read_container_file(blob_name=os.getenv("ded_blob_name"),container_name=os.getenv('dedcontainername'))
    cid_ded_list=BytesIO(result)
    df_ded_list=pd.read_excel(cid_ded_list)

    ## Fetch Query result
    execution_obj=Execution()
    ci_ai_db_server_list=await execution_obj._get_query_result(query=query)
    ci_ai_list=list(itertools.chain.from_iterable(ci_ai_db_server_list))

    ## DED list filtered
    ded_list_filtered=list(df_ded_list['SIDCID'])

    ## From query output select only those which are present in DED List
    updated_ci_ai_list=[elem for elem in ci_ai_list if elem[0]['SIDCID'] in ded_list_filtered]

    ## Unique Zone count for zonal and nonzonal
    unique_zone_count=await execution_obj._get_unique_zone_count(updated_ci_ai_list)
    ci_ai_db_grouping=await execution_obj._get_ci_ai_db_grouping(unique_zone_count)
    zonal_ci_ai=[]
    zonal_db=[]
    nonzonal=[]

    ## Dataframes of zonal and nonzonal
    for elem in ci_ai_db_grouping:
        if elem is not None:
            if elem['Zonal']==True and elem['Type']=="CI/AI":
                zonal_ci_ai.append(elem)
            elif elem['Zonal']==True and elem['Type']=="DB":
                zonal_db.append(elem)
            elif elem['Zonal']==False:
                nonzonal.append(elem)
    dfzonal_ci_ai=pd.DataFrame.from_dict(zonal_ci_ai)
    dfzonal_db=pd.DataFrame.from_dict(zonal_db)
    dfnonzonal=pd.DataFrame.from_dict(nonzonal)
    df_merge_zonal_ci_ai=None
    df_merge_zonal_db=None
    df_merge_nonzonal=None
    ## Creating excel files
    if dfzonal_ci_ai.empty is not True:
        df_merge_zonal_ci_ai=pd.merge(df_ded_list,dfzonal_ci_ai,on="SIDCID",how="inner")
        #df_merge_zonal_ci_ai.to_excel("ded_zonal_ci_ai.xlsx",index=False)
    if dfzonal_db.empty is not True:
        df_merge_zonal_db=pd.merge(df_ded_list,dfzonal_db,on="SIDCID",how="inner")
        #df_merge_zonal_db.to_excel("ded_zonal_db.xlsx",index=False)
    if dfnonzonal.empty is not True:
        df_merge_nonzonal=pd.merge(df_ded_list,dfnonzonal,on="SIDCID",how="inner")
        #df_merge_nonzonal.to_excel("ded_non_zonal.xlsx",index=False)

    #Upload Excel

    result_xlsx=BytesIO()
    
    with pd.ExcelWriter(result_xlsx,engine='openpyxl') as writer:
        if df_merge_zonal_ci_ai is not None:
            df_merge_zonal_ci_ai.to_excel(writer,sheet_name="Zonal CI_AI",index=False)
        if df_merge_zonal_db is not None:
            df_merge_zonal_db.to_excel(writer,sheet_name="Zonal DB",index=False)
        if df_merge_nonzonal is not None:
            df_merge_nonzonal.to_excel(writer,sheet_name="Non Zonal System",index=False)
    
    result_xlsx.seek(0)

    output=await obj.upload_blob_to_container(data=result_xlsx,file_name=os.getenv("zonal_result_file_name"),container_name=os.getenv("resultcontainer"))
    print(output)
    return func.HttpResponse(
             str(output),
             status_code=200
        )