import glob
import shutil
import numpy as np
import os
import pandas as pd

cwd = os.getcwd()
pwd = os.path.dirname(cwd)
dir = input("Input the iteration number province, and scenario in the correct format:\n(iteration_province_scenario in the format, iteration_elecscenario_emissionscenario)\n")
iter = dir.split('_')[0]
for m in iter:
    if m.isdigit():
        iter_num = m
m = int(m)
scen = dir.split('_')[1] + '_' + dir.split('_')[2]
src = f"/mnt/c/silver_lmp/silver_data/model results/ab_2050_{dir.split('_')[0]}_{dir.split('_')[1]}_{dir.split('_')[2]}/"
files = os.listdir(src)
for fname in files:
    shutil.copy2(os.path.join(src, fname), f'{pwd}/{dir}')

if len(dir.split("_")) > 3:
    sen = os.path.join(pwd, f'iter{m+1}_{scen}_{dir.split("_")[3]}')

else:
    sen = os.path.join(pwd, f'iter{m+1}_{scen}')
    
os.makedirs(sen, exist_ok=True)   

os.chdir(f'{pwd}/{dir}')

###Post processing SILVER results###
extension = 'csv'
vre_filenames = [i for i in glob.glob('Available_VRE_generation*.{}'.format(extension))]
combined_available_vre = pd.concat([pd.read_csv(f, index_col=0) for f in vre_filenames], axis=0)
combined_available_vre.index = pd.to_datetime(combined_available_vre.index, unit='h' ,dayfirst=True, origin='2050-01-01')
combined_available_vre = combined_available_vre.drop(columns='date')

uc_filenames = [i for i in glob.glob('UC_Results_*.{}'.format(extension))]
header = list(pd.read_csv(uc_filenames[0], header=None).loc[14,:])
header = [x for x in header if str(x) != 'nan' and x != 'name']
header.insert(0,'date')
combined_uc = pd.concat([pd.read_csv(f, skiprows=[i for i in range(1,30)], index_col=0,skipfooter=749, engine='python') for f in uc_filenames])
combined_uc.reset_index(inplace=True)
combined_uc.index = pd.to_datetime(combined_uc.index, unit='h', dayfirst=True, origin='2050-01-01')
combined_uc = combined_uc.drop(columns=['Total','dr'])
combined_uc.columns = header
combined_uc = combined_uc.drop(columns=['date'])
combined_uc_vre = combined_uc[list(combined_uc.filter(regex='^Wind|^Solar'))]

lf_filenames = [i for i in glob.glob('Line_Flow_*.csv')]
header = pd.DataFrame(pd.read_csv(lf_filenames[0]))
header = header.iloc[:,[0,1]]
combined_lf = pd.concat([(pd.read_csv(f, header=None)) for f in lf_filenames], axis=1)
combined_lf = combined_lf.transpose()
combined_lf.index = combined_lf[0]
combined_lf = combined_lf.drop(columns=[0])
combined_lf = combined_lf.drop(index=['from','to'])
combined_lf.reset_index(inplace=True)
combined_lf = combined_lf.drop(columns=[0])
combined_lf.index = pd.to_datetime(combined_lf.index, unit='h', dayfirst=True, origin='2050-01-01')
combined_lf.columns = pd.MultiIndex.from_frame(header)
combined_lf = combined_lf.astype(float)

congestion = pd.DataFrame(index=combined_lf.index, columns=range(83))
congestion.columns = pd.MultiIndex.from_frame(header)

#PMAX mehod should be depreciated as not accurate. USE LMP instead
"""try:
    shutil.copy2(f'{pwd}/iter{m-1}_{scen}/pmax.xlsx', f'{pwd}/{dir}')
except:
    print('Provide PMax data for this scenario')

try:
    pmax = pd.read_excel('pmax.xlsx', index_col=0, header=None)
except:
    print('Provide PMAX data for this scenario')

pmax = pmax.drop(['from','to'])
pmax.columns = pd.MultiIndex.from_frame(header)
pmax = pd.concat([pmax]*1440)
pmax.index = combined_lf.index

for column in combined_lf.columns:
    congestion[column] = np.where(combined_lf[column] > 0.85*pmax[column], 1, 0)"""

congestion['Any congested lines'] = congestion.any(axis=1)

total_avail = combined_available_vre.sum()
total_avail.name = 'total'
combined_available_vre.loc[len(combined_available_vre),] = total_avail
total_gen = combined_uc_vre.sum()
total_gen.name = 'total'
combined_uc_vre.loc[len(combined_uc_vre)] = total_gen

curtailment_rate = pd.DataFrame(index=combined_uc_vre.index)
curtailment_rate['Total Available Wind'] = combined_available_vre[list(combined_uc.filter(regex='^Wind'))].sum(axis=1)
curtailment_rate['Total Dispatched Wind'] = combined_uc_vre[list(combined_uc.filter(regex='^Wind'))].sum(axis=1)
curtailment_rate.loc[len(curtailment_rate)] = curtailment_rate.sum()
curtailment_rate.index.values[-1] = 'Total'
curtailment_rate['Total Curtailed Wind'] = 100*(1-curtailment_rate['Total Dispatched Wind']/curtailment_rate['Total Available Wind'])
curtailment_rate = curtailment_rate.drop(1440)

curtailment = 100* (1 - combined_uc_vre / combined_available_vre)
curtailment.loc[len(curtailment)] = total_avail
curtailment.loc[len(curtailment)] = total_gen
curtailment = pd.concat([curtailment, curtailment_rate], axis=1)
curtailment.index.values[-3:] = ['curtailed percentage', 'available generation', 'actual generation']


combined_uc.loc[len(combined_uc)] = combined_uc.sum()
combined_uc.index.values[-1] = 'sum'
combined_uc_vre[len(combined_uc_vre)] = combined_uc_vre.sum()
combined_uc_vre.index.values[-1] = 'sum'

###Translating LMP results into setpoint measures###
all_filenames = [i for i in glob.glob('LMP*.{}'.format(extension))]
combined_lmp = pd.concat([pd.read_csv(f, index_col=0) for f in all_filenames], axis=1)

lmp_hourly = combined_lmp.T
lmp_hourly.reset_index(drop=True, inplace=True)
lmp_hourly.index = pd.to_datetime(lmp_hourly.index, unit='h', dayfirst=True, origin='2050-01-01')
lmp_hourly['mean'] = lmp_hourly.mean(axis=1)

analysis = pd.DataFrame(index=curtailment_rate.index)
analysis['Curtailed Wind'] = curtailment_rate['Total Curtailed Wind']
analysis['LMP(mean)'] = lmp_hourly['mean']
analysis['Load'] = combined_uc.sum(axis=1)

writer = pd.ExcelWriter(f'analysis_{dir}.xlsx', engine='xlsxwriter')
analysis.to_excel(writer, sheet_name="Analysis", encoding='UTF-8')
combined_uc.to_excel(writer, sheet_name="UC Results", encoding='UTF-8')
combined_uc_vre.to_excel(writer, sheet_name="UC VRE Results", encoding='UTF-8')
combined_lf.to_excel(writer, sheet_name="Line Flow", encoding='UTF-8')
combined_available_vre.to_excel(writer, sheet_name="Available VRE", encoding='UTF-8')
combined_lmp.to_excel(writer, sheet_name="LMP Results", encoding='UTF-8')
curtailment.to_excel(writer, sheet_name="Curtailment Details", encoding='UTF-8')
congestion.to_excel(writer, sheet_name="Congestion Analysis", encoding='UTF-8')
writer.save()

load = pd.read_csv(f"loads_{dir.split('_')[0]}_{dir.split('_')[1]}_{dir.split('_')[2]}.csv", index_col=0)

load = load[['residential_cooling', 'residential_heating']].reset_index(drop=True)
load.index = pd.to_datetime(load.index, unit='h', dayfirst=True, origin='2050-01-01')

lmp_daily = pd.DataFrame()
el_upper = 0.90
el_lower = 0.10

lmp_daily['sp_max'] = lmp_hourly['mean'].groupby(np.arange(len(lmp_hourly))//24).max()
lmp_daily['sp_min'] = lmp_hourly['mean'].groupby(np.arange(len(lmp_hourly))//24).min()
lmp_daily['hpt'] = lmp_daily['sp_min'] + el_upper*(lmp_daily['sp_max']-lmp_daily['sp_min'])
lmp_daily['lpt'] = lmp_daily['sp_min'] + el_lower*(lmp_daily['sp_max']-lmp_daily['sp_min'])
lmp_daily.reset_index(drop=True, inplace=True)
lmp_daily.index = pd.to_datetime(lmp_daily.index, unit='D', dayfirst=True, origin='2050-01-01')
#lmp_daily.to_csv('temp.csv')

htgfile = open('htg_measure.txt', 'w+')

#testing with only 5 months
#lmp_hourly = lmp_hourly.loc[lmp_hourly.index.month == [1,2,3,4]]

Rubystringhtg = 'ems_htg_setpoint_prg.addLine'
Rubystringclg = 'ems_clg_setpoint_prg.addLine'

max_sp_winter = 23
min_sp_winter = 20
mean_sp_winter = 21
max_sp_summer = 27
min_sp_summer = 23
mean_sp_summer = 25

lastmonth = 0
lastday = 0
setpoint_counter = 0
monthly_hours = 0

changed_sp = pd.DataFrame(index = combined_lf.index)
changed_sp['changed'] = np.nan
'''try:
    changed_sp_prev = pd.read_csv(f'{pwd}/iter{m-1}_{scen}/changed_sp_iter{m-1}_{scen}.csv', index_col=0)
    changed_sp['changed'] = changed_sp_prev['changed'].to_numpy()
except:
    print('This is the first iteration for changing setpoints')'''

loads_prev = pd.read_csv(f"{pwd}/{dir}/loads_{dir.split('_')[0]}_{dir.split('_')[1]}_{dir.split('_')[2]}.csv", index_col=0)

loads_prev.drop(loads_prev.tail(1).index, inplace=True)
loads_prev.reset_index(drop=True, inplace=True)
loads_prev.index = pd.to_datetime(loads_prev.index, unit='h', dayfirst=True, origin='2050-01-01')
loads = loads_prev
loads_prev = loads_prev.iloc[0:1440]

loads_daily = pd.DataFrame()
test = np.arange(len(loads_prev))//24
loads_daily['daily_max'] = loads_prev['demand'].groupby(np.arange(len(loads_prev))//24).max()
loads_daily['daily_min'] = loads_prev['demand'].groupby(np.arange(len(loads_prev))//24).min()
ldt = 0.88 #loads drop thershold
hdt = 0.11 #loads increase
loads_daily['ldt'] = loads_daily['daily_min'] + ldt * (loads_daily['daily_max'] - loads_daily['daily_min'])
loads_daily['hdt'] = loads_daily['daily_min'] + hdt * (loads_daily['daily_max'] - loads_daily['daily_min'])
loads_daily.index = pd.to_datetime(loads_daily.index, unit='D', dayfirst=True, origin='2050-01-01')

lastmonth = 0
lastday = 0

for index,values in loads_prev.iterrows():
    
    currentmonth = index.month
    currentday = index.day
    hour = index.hour

    #separate seasons, winter, based on the load calculation files out of base load
    if load.loc[(load.index.hour == hour) & (load.index.day == currentday) & (load.index.month == currentmonth), 'residential_heating'][0] != 0 and \
        ((values['demand'] > loads_daily.loc[(loads_daily.index.day == currentday) & (loads_daily.index.month == currentmonth), 'ldt'][0] and
        lmp_hourly['mean'].loc[index] > lmp_daily.loc[(lmp_daily.index.day == currentday) & (lmp_daily.index.month == currentmonth), 'hpt'][0]) or \
        (values['demand'] < loads_daily.loc[(loads_daily.index.day == currentday) & (loads_daily.index.month == currentmonth), 'ldt'][0] and 
        lmp_hourly['mean'].loc[index] < lmp_daily.loc[(lmp_daily.index.day == currentday) & (lmp_daily.index.month == currentmonth), 'lpt'][0])):
        #and changed_sp['changed'].loc[index] != True:

        if currentmonth != lastmonth:
            monthly_hours = 0
            if lastmonth == 0:
                htgfile.write(F'{Rubystringhtg}(\"IF (Month == {index.month}) \") \n' )
            else:
                if lastday != 0:
                    htgfile.write(F'{Rubystringhtg}(\"ENDIF\")\n') # matching if: day == 1 or hour == 14?
                htgfile.write(F'{Rubystringhtg}(\"ENDIF\")\n') # matching if = day == 1 or hour == 14?
                htgfile.write(F'{Rubystringhtg}(\"ELSEIF (Month == {index.month}) \") \n' )             
        
        if currentday != lastday:
            setpoint_counter = 0
            if monthly_hours == 0:
                #if lastday != 0:
                    #htgfile.write(F'{Rubystringhtg}(\"ENDIF\")\n') # matching if: day == 1 or hour == 14?
                    
                htgfile.write(F'{Rubystringhtg}(\"IF (DayOfMonth == {index.day}) \") \n' )
                    
            elif changed_sp.loc[changed_sp.index.day == currentday-1,'changed'].any():
                htgfile.write(F'{Rubystringhtg}(\"ENDIF\")\n')
                htgfile.write(F'{Rubystringhtg}(\"ELSEIF (DayOfMonth == {index.day}) \") \n' )
                       
        #decrease the setpoint, if higher than HPT
        if values['demand'] > loads_daily.loc[(loads_daily.index.day == currentday) & (loads_daily.index.month == currentmonth), 'ldt'][0] and \
            lmp_hourly['mean'].loc[index] > lmp_daily.loc[(lmp_daily.index.day == currentday) & (lmp_daily.index.month == currentmonth), 'hpt'][0]:
            if setpoint_counter == 0:
                htgfile.write(F'{Rubystringhtg}(\"IF (Hour == {index.hour}) \") \n' )
            else:
                htgfile.write(F'{Rubystringhtg}(\"ELSEIF (Hour == {index.hour-1}) \") \n' )
            htgfile.write(F'{Rubystringhtg}(\"SET #{{ems_htg_sch_actuator.name}} = {min_sp_winter}\") \n')
            setpoint_counter += 1
            changed_sp['changed'].loc[index] = True

        #increase the setpoint, if lower than LPT
        elif values['demand'] < loads_daily.loc[(loads_daily.index.day == currentday) & (loads_daily.index.month == currentmonth), 'hdt'][0] and \
            lmp_hourly['mean'].loc[index] < lmp_daily.loc[(lmp_daily.index.day == currentday) & (lmp_daily.index.month == currentmonth), 'lpt'][0]:
            if setpoint_counter == 0:
                htgfile.write(F'{Rubystringhtg}(\"IF (Hour == {index.hour}) \") \n' )
            else:
                htgfile.write(F'{Rubystringhtg}(\"ELSEIF (Hour == {index.hour-1}) \") \n' )
            htgfile.write(F'{Rubystringhtg}(\"SET #{{ems_htg_sch_actuator.name}} = {max_sp_winter}\") \n')
            setpoint_counter += 1
            changed_sp['changed'].loc[index] = True

        else:
            setpoint_counter == 0
       
        monthly_hours += 1

        lastmonth = currentmonth
        lastday = currentday

changed_sp.to_csv(f'changed_sp_{dir}.csv')

# setpoint for non-curtailment hours
htgfile.write(F'{Rubystringhtg}(\"ENDIF\")\n')
htgfile.write(F'{Rubystringhtg}(\"ENDIF\")\n')
htgfile.write(F'{Rubystringhtg}(\"ELSE\")\n')
htgfile.write(F'{Rubystringhtg}(\"SET #{{ems_htg_sch_actuator.name}} = {mean_sp_winter}\")\n')
htgfile.write(F'{Rubystringhtg}(\"ENDIF\")\n')  # matching "if" = January (if month == 1)

htgfile.close()

shutil.copy2(f'{pwd}/measure.rb', sen)

with open('htg_measure.txt', 'rt') as htg_mes:
    tstat_lines = htg_mes.readlines()

os.chdir(sen)
with open('measure.rb', 'rt') as measure_file:
    measure_lines = measure_file.readlines()

with open('measure.rb', 'w') as measure_file:
    for i,line in enumerate(measure_lines):
        if i == 43:
            measure_file.writelines(f'    return "iter{m+1}_{scen} Computed Schedule"')
        elif i == 343:
            measure_file.writelines('    ' + lin for lin in tstat_lines)
        else:
            measure_file.writelines(line) 
shutil.copy2(f'measure.rb', f'/mnt/c/users/smoha/documents/archetypes_base/measures/DR_measure_setpoint_iter{m+1}/')
os.chdir(f'{pwd}/{dir}')

clgfile = open('clg_measure.txt', 'w+')

lastmonth = 0
lastday = 0

for index,values in lmp_hourly.iterrows():
    
    currentmonth = index.month
    currentday = index.day
    hour = index.hour

    #separate seasons, summer, based on the load calculation files out of base load
    if load.loc[(load.index.hour == hour) & (load.index.day == currentday) & (load.index.month == currentmonth), 'residential_cooling'][0] != 0:
                      
        #increse the setpoint, if higher than HPT
        if values['mean'] > lmp_daily.loc[(lmp_daily.index.day == currentday) & (lmp_daily.index.month == currentmonth), 'hpt'][0]:
            if setpoint_counter == 0:
                clgfile.write(F'{Rubystringclg}(\"IF (Hour == {index.hour}) \") \n' )
            else:
                clgfile.write(F'{Rubystringclg}(\"ELSEIF (Hour == {index.hour}) \") \n' )
            clgfile.write(F'{Rubystringclg}(\"SET #{{ems_clg_sch_actuator.name}} = {max_sp_summer}\") \n')
            setpoint_counter += 1

        #decrease the setpoint, if lower than LPT
        elif values['mean'] < lmp_daily.loc[(lmp_daily.index.day == currentday) & (lmp_daily.index.month == currentmonth), 'lpt'][0]:
            if setpoint_counter == 0:
                clgfile.write(F'{Rubystringclg}(\"IF (Hour == {index.hour}) \") \n' )
            else:
                clgfile.write(F'{Rubystringclg}(\"ELSEIF (Hour == {index.hour}) \") \n' )
            clgfile.write(F'{Rubystringclg}(\"SET #{{ems_clg_sch_actuator.name}} = {min_sp_summer}\") \n')
            setpoint_counter += 1

        else:
            setpoint_counter == 0
       
        monthly_hours += 1

    lastmonth = currentmonth
    lastday = currentday

# setpoint for non-curtailment hours
clgfile.write(F'{Rubystringclg}(\"ELSE\")\n')
clgfile.write(F'{Rubystringclg}(\"SET #{{ems_htg_sch_actuator.name}} = {mean_sp_summer}\")\n')
clgfile.write(F'{Rubystringclg}(\"ENDIF\")\n')  # matching "if" = January (if month == 1)

clgfile.close()