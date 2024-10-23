import logging
import asyncio
from services.auth_service import AuthService
from services.graph_service import GraphService
from services.subscription_service import SubscriptionService
from shared_code.utilities import get_groupby,sort_server_list_function,update_dict_func
import collections
class Execution(object):

    def __init__(self) -> None:
        pass
    
    # segregate CI/AI and DB servers
    def _group_ci_ai_db_function(self,_groupby_on_appid):
        _ci_ai_server_list=[]
        _db_server_list=[]
        try:
            
            for elem in _groupby_on_appid:
                if elem[0]['appid'] == 'CI' or elem[0]['appid'] == 'AI':
                    _ci_ai_server_list.extend(elem)
                else:
                    _db_server_list.extend(elem)

            ci_ai_vm_list,db_vm_list=None,None
            zone_division_ci_ai=collections.Counter(e['zones'][0] for e in _ci_ai_server_list)
            zone_division_db=collections.Counter(e['zones'][0] for e in _db_server_list)
            appid_division_ci_ai=collections.Counter(e['appid'] for e in _ci_ai_server_list)
            appid_division_db=collections.Counter(e['appid'] for e in _db_server_list)
            ci_ai_vm_list=[e['name'] for e in _ci_ai_server_list]
            db_vm_list=[e['name'] for e in _db_server_list]
            
            if len(_ci_ai_server_list) !=0 :
                sid_cid=_ci_ai_server_list[0]['SIDCID']
            elif len(_db_server_list) !=0 :
                sid_cid=_db_server_list[0]['SIDCID']
            else:
                sid_cid='Not Present'
            
            if ci_ai_vm_list is not None:
                if len(zone_division_ci_ai)==1:
                    _groupby_appid_result_dict={
                        'SIDCID':sid_cid,
                        'LandscapeID':_ci_ai_server_list[0]['LandscapeID'],
                        'Zone Division Count of VM in Each Zone CI/AI':update_dict_func(zone_division_ci_ai,keyword='Zone'),
                        'Total Server CI':appid_division_ci_ai['CI'] if 'CI' in appid_division_ci_ai.keys() else 0,
                        'Total Server AI':appid_division_ci_ai['AI'] if 'AI' in appid_division_ci_ai.keys() else 0,
                        'CI/AI VM List':str(ci_ai_vm_list),
                        'Zonal':True,
                        'Type':'CI/AI',
                        'Message': 'All CI/AI servers are in single zone'
                    }
                    return _groupby_appid_result_dict
                
                elif len(zone_division_ci_ai)==2:
                    zonekeys=list(zone_division_ci_ai.keys())
                    if zone_division_ci_ai[zonekeys[0]]!=zone_division_ci_ai[zonekeys[1]]:
                        _groupby_appid_result_dict={
                            'SIDCID':sid_cid,
                            'LandscapeID':_ci_ai_server_list[0]['LandscapeID'],
                            'Zone Division Count of VM in Each Zone CI/AI':update_dict_func(zone_division_ci_ai,keyword='Zone'),
                            'Total Server CI':appid_division_ci_ai['CI'] if 'CI' in appid_division_ci_ai.keys() else 0,
                            'Total Server AI':appid_division_ci_ai['AI'] if 'AI' in appid_division_ci_ai.keys() else 0,
                            'CI/AI VM List':str(ci_ai_vm_list),
                            'Zonal':True,
                            'Type':'CI/AI',
                            'Message': 'CI/AI server Zones are not evenly distributed across zones'
                            }
                        return _groupby_appid_result_dict

            if db_vm_list is not None:
                if len(zone_division_db)==1:
                    _groupby_appid_result_dict={
                        'SIDCID':sid_cid,
                        'LandscapeID':_db_server_list[0]['LandscapeID'],
                        'Zone Division Count of VM in Each Zone DB':update_dict_func(zone_division_db,keyword='Zone'),
                        'Total Server DB':list(appid_division_db.values())[0] if len(appid_division_db)!=0 else 0,
                        'DB VM List':str(db_vm_list),
                        'Zonal':True,
                        'Type': 'DB',
                        'Message':'All DB servers are in single zone'
                    }
                    return _groupby_appid_result_dict
                
                elif len(zone_division_db)==2:
                    zonekeys=list(zone_division_db.keys())
                    if zone_division_db[zonekeys[0]]!=zone_division_db[zonekeys[1]]:
                        _groupby_appid_result_dict={
                            'SIDCID':sid_cid,
                            'LandscapeID':_db_server_list[0]['LandscapeID'],
                            'Zone Division Count of VM in Each Zone DB':update_dict_func(zone_division_db,keyword='Zone'),
                            'Total Server DB':list(appid_division_db.values())[0] if len(appid_division_db)!=0 else 0,
                            'DB VM List':str(db_vm_list),
                            'Zonal':True,
                            'Type': 'DB',
                            'Message':'DB server Zones are not evenly distributed across zones'
                        }
                        return _groupby_appid_result_dict
        except Exception as e:
            logging.error(f"Error with grouping of data {e}")
            return None
    
    async def _appid_grouping_function(self,server_app_list):
        try:
            countuniquezone=server_app_list['uniquezone']
            sid_cid_data=server_app_list['data']
            if countuniquezone == None:
                vm_list=[e['name'] for e in sid_cid_data]
                sid_cid=None
                if sid_cid_data is not None:
                    sid_cid=sid_cid_data[0]['SIDCID']
                res_dict={
                    'non_zonal_vm_list':vm_list,
                    'SIDCID':sid_cid,
                    'Zonal':False
                }
                return res_dict
            elif len(countuniquezone) == 1 or len(countuniquezone) == 2:
                _groupby_parameter='appid'
                _sorted_sublist_serverlist=await sort_server_list_function(sid_cid_data,_groupby_parameter)
                _groupby_on_appid=await get_groupby(_sorted_sublist_serverlist,_groupby_parameter)
                _groupby_appid_result_dict=self._group_ci_ai_db_function(_groupby_on_appid)

                return _groupby_appid_result_dict
        except Exception as e:
            logging.error(f"Error with grouping of appid {e}")
            return None
    
    # Grouping of servers
    async def _get_ci_ai_db_grouping(self,unique_zone_count_server):
        appid_grouping_result=[]
        appid_grouping_result=await asyncio.gather(
            *(asyncio.create_task(
                self._appid_grouping_function(server_appid_list)
            )for server_appid_list in unique_zone_count_server)
        )
        return appid_grouping_result
    
    # Get Unique Zone 
    async def __get_unique_zone_function(self,server):
        try:
            #logging.info(server)
            zones_count=collections.Counter(e['zones'][0] for e in server)
            unique_zone_dict={
                "uniquezone":zones_count,
                "data":server
            }
            return unique_zone_dict
        except Exception as e:
            non_zonal_deployment={
                "uniquezone":None,
                "data":server
            }
            logging.info(f"Non zonal")
            return non_zonal_deployment
    
    # Segregate servers on basis of zones
    async def _get_unique_zone_count(self,ci_ai_db_server_list):
        zone_count_result=[]
        try:
            zone_count_result=await asyncio.gather(
                *(
                    asyncio.create_task(
                        self.__get_unique_zone_function(server)
                    )for server in ci_ai_db_server_list
                )
            )
        except Exception as e:
            logging.error(f"Error with unique zones {e}")
            return None
        return zone_count_result

    # Execute Query across both tenant
    async def __run_query_tenant(self,query:str,cred:str):
        server_tenant_dict={}
        try:
            credential,cloud=AuthService.get_credential(credential_key=cred)
            async with credential:
                subscriptions=await SubscriptionService.subscription_list(credentials=credential,cloud=cloud)
                sub_ids=SubscriptionService.filter_ids(subscriptions)
                server_list=await GraphService.run_query(
                    query_str=query,
                    credential=credential,
                    sub_ids=sub_ids,
                    cloud=cloud
                )
            server_tenant_dict={
                "credential_key":cred,
                "data":server_list
            }
            _groupby_parameter='SIDCID'
            _sorted_server_list=await sort_server_list_function(server_tenant_dict['data'],_groupby_parameter)
            _groupby_on_sidcid=await get_groupby(_sorted_server_list,_groupby_parameter)
            return _groupby_on_sidcid
        except Exception as e:
            logging.error(f"Error with Running the query and grouping it {e}")
            return None

    # Co-routine to run query
    async def _get_query_result(self,query:str):
        try:
            credential_list=AuthService.get_credential_keys()
            result=[]
            result=await asyncio.gather(
                *(asyncio.create_task(
                    self.__run_query_tenant(query,cred)
                )for cred in credential_list)
            )
            return result
        except Exception as e:
            logging.error(f"Error fetching query {e}")
            return []
