# EU_HFR_NODE_radialStatus
Python3 scripts for checking and reporting the status of the radial data availability for the HFR stations connected to the the European HFR Node (EU HFR Node). Tools to be run at the EU HFR Node.

This application is written in Python3 language and is based on a MySQL database containing information about data and metadata. The application is designed for High Frequency Radar (HFR) data management according to the European HFR node processing workflow, thus reading from the EU HFR NODE database information about radial delay and number of velocity vectors contained in radial files received from each HFR system connected to the Node.
The radial delay is defined as the difference in hours between the run time rounded at o'clock hour and the datetime of the last radial data available from each HFR station.

The database is composed by the following tables:
- account_tb: it contains the general information about HFR providers and the HFR networks they manage.
- network_tb: it contains the general information about the HFR network producing the radial and total files. These information will be used for the metadata content of the netCDF files.
- station_tb: it contains the general information about the radar sites belonging to each HFR network producing the radial files. These information will be used for the metadata content of the netCDF files.
- radial_input_tb: it contains information about the radial files to be converted and combined into total files.
- radial_HFRnetCDF_tb: it contains information about the converted radial files.
- total_input_tb: it contains information about the total files to be converted.
- total_HFRnetCDF_tb: it contains information about the combined and converted total files.
- radial_delay_tb: it contains information about the last available data and radial delay from each HFR system.

The application first checks in the radial_delay_tb of the EU HFR NODE database if there are delays larger than the input threshold in the synchronization of the radial files from the measurement sites. If no synchronization delay occurs for a specific station, the application checks how many radial files were synchronized in the last number of hours with a number of radial velocity vectors lower than the Radial Count QC test threshold set for that station. This check is performed by querying the radial_input_tb of the EU HFR NODE database. If, for any station, a synchronization delay occurs or files with a critically low number of velocity vectors were synchronized in the last number of hours, a mail containing these critical status information is sent to the contact email reported in the EU HFR NODE database.

When calling the application it is possible to specify the synchronization delay which triggers the email notification. If no input is specified, 12 hours delay is set as triggering delay.

The application EU_HFR_NODE_radialStatus.py has to be run with a frequency equal to the input delay (default 12 hours) and it is launched via the crontab scheduler. 
General information for the tables network_tb and station_tb are loaded onto the database via a webform to be filled by the data providers. The webform is available at https://webform.hfrnode.eu

Usage: HFR-TirLig_radialStatus.py -d <synchronization delay in hours, default to 12 hours>

The required packages are:
- sys
- getopt
- logging
- datetime as dt
- pandas as pd
- sqlalchemy
- smtplib
- email.message

The guidelines on how to synchronize the providers' HFR radial and total data towards the EU HFR Node are available at ​https://doi.org/10.25704/9XPF-76G7
How to cite:
- when using these guidelines, ​please use the following citation carefully and correctly​:
Reyes, E., Rotllán, P., Rubio, A., Corgnati, L., Mader, J., & Mantovani, C. (2019).
Guidelines on how to sync your High Frequency (HF) radar data with the European HF
Radar node (Version 1.1). Balearic Islands Coastal Observing and Forecasting System,
SOCIB . https://doi.org/10.25704/9XPF-76G7

Cite as:
Lorenzo Corgnati. (2026). EU_HFR_NODE_radialStatus. DOI: 10.5281/zenodo.20746552


Author: Lorenzo Corgnati

Date: June 18, 2026

E-mail: lorenzopaolo.corgnati@cnr.it
