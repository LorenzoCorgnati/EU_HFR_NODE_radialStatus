#!/usr/bin/python3


# Created on Tue Jun 16 16:18:38 2026

# @author: Lorenzo Corgnati
# e-mail: lorenzopaolo.corgnati@cnr.it


# This application checks and reports the status of the radial data availability for the HFR-TirLig network.
# The application first checks in the radial_delay_tb of the EU HFR NODE database if there are delays larger 
# than the input threshold in the synchronization of the radial files from the measurement sites. 
# If no synchronization delay occurs for a specific station, the application checks how many radial files were 
# synchronized in the last 24 hours with a number of radial velocity vectors lower than the Radial Count QC test threshold
# set for that station. This check is performed by querying the radial_input_tb of the EU HFR NODE database.
# If, for any station, a synchronization delay occurs or files with a critically low number of velocity vectors were 
# synchronized in the last 24 hours, a mail containing these critical status information is sent to the contact email
# reported in the EU HFR NODE database.

# When calling the application it is possible to specify the synchronization delay which triggers the email notification.
# If no input is specified, 12 hours delay is set as triggering delay.

import sys
import getopt
import logging
import datetime as dt
import pandas as pd
import sqlalchemy
import smtplib
from email.message import EmailMessage

def sendAlertEmail(alertDF,networkData,delay,logger):
    """
    This function sends an email to the contact emails of the HFR network alerting about the stations with synchronization delay
    greater than the input threshold and the number of radial files with a critically low number of velocity vectors sent in the
    defined time interval.
    
    The email is sent from the info@hfrnode.eu email address and is formatted in HTML for better readability. 
    
    INPUTS:
        alertDF: DataFrame containing the information about the stations with critical synchronization delay or 
                  critically low number of velocity vectors in the radial files synchronized in the defined time interval
        networkData: DataFrame containing the network information
        delay: the time interval for which to check radial file synchronization
        logger: logger object of the current processing

        
    OUTPUTS:
        
    """
    #####
    # Setup
    #####
    
    # Initialize error flag
    aeErr = False

    # Set the email parameters
    smtpServer = 'smtpauth.ismar.cnr.it'
    smtpPort = 465
    fromAddress = 'info@hfrnode.eu'
    password = '#JSSvgmEezYx'

    try:

    #####
    # Create the email content
    #####
        # Get the destination recipient
        addresses = networkData['contributor_email'].iloc[0]
        if ';' in addresses:
            toAddress = [part.strip() for part in addresses.split(";") if part.strip()]

        # Set the email subject and recipients
        msg = EmailMessage()
        msg["Subject"] = 'Issues in radial synchronization for the ' + networkData['network_id'].iloc[0] + ' network - ' + dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        msg["From"] = fromAddress
        msg["To"] = ", ".join(toAddress)

        # Create the body HTML version: <b> for bold, <br> for line breaks
        htmlBody = """\
        <html>
            <body>
        """

        # Compose the body part related to critical synchronization delay
        if (alertDF['number_of_radials_below_threshold'] == 0).any():
            # Create the body plain-text fallback: \n for line breaks, no real bold
            plainBody = (
                "Stations with critical synchronization delay:\n\n"
            )        

            # Compose the HTML body with the critical radial delay information
            htmlBody += """\
                <p><b>Stations with critical synchronization delay:</b><br><br></p>
            """

            # Iterate over the rows of the alertDF and add the information about the stations with critical synchronization delay to the email body
            for index, row in alertDF.iterrows():
                if row['number_of_radials_below_threshold'] != 0:
                    pass
                else:
                    plainBody += f" - {row['station_id']} is not sending data for {row['radial_delay']} hours\n"
                    htmlBody += f" <p><strong>{row['station_id']}</strong> is not sending data for {row['radial_delay']} hours<br></p>\n"

            # Insert a line break between the two sections of the email body
            plainBody += f" - \n\n"
            htmlBody += f" <p><br><br></p>\n"

        if (alertDF['number_of_radials_below_threshold'] != 0).any():
            # Compose the body with the information about radials with critically low number of velocity vectors
            plainBody += "Stations with critically low number of velocity vectors:\n\n"
            htmlBody += """\
                <p><b>Stations with critically low number of velocity vectors:</b><br><br></p>
        """

            # Iterate over the rows of the alertDF and add the information about the stations with critically low number of velocity vectors to the email body
            for index, row in alertDF.iterrows():
                if row['number_of_radials_below_threshold'] == 0:
                    pass
                else:
                    plainBody += f" - {row['station_id']} sent {row['number_of_radials']} radial files in the last {delay} hours, {row['number_of_radials_below_threshold']} of which containing less than {row['radial_QC_radial_count_threshold']} velocity vectors\n"
                    htmlBody += f" <p><strong>{row['station_id']}</strong> sent {row['number_of_radials']} radial files in the last {delay} hours, {row['number_of_radials_below_threshold']} of which containing less than {row['radial_QC_radial_count_threshold']} velocity vectors<br></p>\n"

        # Close the HTML body
        htmlBody += """\
            </body>
        </html>
        """

        msg.set_content(plainBody)
        msg.add_alternative(htmlBody,subtype="html")

        with smtplib.SMTP_SSL(smtpServer,smtpPort) as server:
            server.login(fromAddress,password)
            server.send_message(msg)

    except Exception as err:
        aeErr = True
        logger.error(err.args[0] + ' in sending the alert email.')

    return aeErr

def getRadialCount(siteInfo,delay,eng,logger):
    """
    This function queries the radial_input_tb table of the EU HFR NODE database for getting the information 
    about the number of radial velocity vectors contained into the radial files synchronized in the time interval 
    given in input by the radial site specified in the input
    The function returns a Series containing the number of radial files synchronized in the defined time interval and 
    how many of them have a number of radial velocity vectors lower than the Radial Count QC test threshold set for that station.
    
    INPUTS:
        siteInfo: Series containing the radial site IDs
        delay: the time interval in hours where to check the number of velocity vecotrs contained into radial files
        eng: SQLAlchemy engine for connecting to the Mysql EU HFR NODE EU HFR NODE database
        logger: logger object of the current processing

        
    OUTPUTS:
        radCount = Series containing the number of radial files synchronized in the defined time interval and 
                    how many of them have a number of radial velocity vectors lower than the input threshold.
        
    """
    #####
    # Setup
    #####
    
    # Initialize error flag
    rcErr = False

    # Create the output DataFrame
    radCount = pd.DataFrame(columns=['station_id', 'number_of_radials', 'number_of_radials_below_threshold'])

    try:
        # Get the station ID
        stationID = siteInfo['station_id']

        # Get the minimum number of radial velocity vectors threshold for the station
        radCntThreshold = siteInfo['radial_QC_radial_count_threshold']

        # Set and execute the query and get the information about the number of radials synchronized in the defined time interval for the HFR station
        syncRadSelectQuery = 'SELECT station_id, number_of_vectors FROM radial_input_tb WHERE station_id=\'' + stationID + '\' AND datetime >= TIMESTAMP(DATE_FORMAT(UTC_TIMESTAMP() - INTERVAL ' + str(delay) + ' HOUR, \'%Y-%m-%d %H:00:00\'))'
        synchRadData = pd.read_sql(syncRadSelectQuery, con=eng)
        logger.info('Radial count data successfully fetched from EU HFR NODE database for site ' + stationID + '.')

        # Wrap the number of radials and the number of radials below the threshold in the output Series
        radCount.loc[0] = [stationID, len(synchRadData), synchRadData['number_of_vectors'].lt(radCntThreshold).sum()]

    except sqlalchemy.exc.DBAPIError as err:        
        rcErr = True
        logger.error('MySQL error ' + err._message())

    return radCount

def getRadialDelay(siteID,eng,logger):
    """
    This function queries the radial_delay_tb table of the EU HFR NODE database for getting the information 
    about the delay in radial synchronization for the radial site specified in the input
    The function returns a Series containing the synchronization delay information for the specified radial site.
    
    INPUTS:
        siteID: Series containing the radial site IDs
        eng: SQLAlchemy engine for connecting to the Mysql EU HFR NODE EU HFR NODE database
        logger: logger object of the current processing

        
    OUTPUTS:
        radDelay = Series containing the information about the delay in radial synchronization for the radial site
        
    """
    #####
    # Setup
    #####
    
    # Initialize error flag
    rdErr = False

    # Create the output DataFrame
    radDelay = pd.DataFrame(columns=['station_id', 'radial_delay'])

    try:
        # Get the station ID
        stationID = siteID['station_id']

        # Set and execute the query and get the synchronization delay for the HFR station
        delaySelectQuery = 'SELECT station_id, radial_delay FROM radial_delay_tb WHERE station_id=\'' + stationID + '\' AND creation_date = (SELECT MAX(creation_date) FROM radial_delay_tb)'
        radDelay = pd.read_sql(delaySelectQuery, con=eng)
        logger.info('Radial delay data successfully fetched from EU HFR NODE database for site ' + stationID + '.')

    except sqlalchemy.exc.DBAPIError as err:        
        rdErr = True
        logger.error('MySQL error ' + err._message())

    return radDelay

####################
# MAIN DEFINITION
####################

def main(argv):
    
#####
# Setup
#####
       
    # Set the argument structure
    try:
        opts, args = getopt.getopt(argv,"d:h",["delay=","help"])
    except getopt.GetoptError:
        print("Usage: HFR-TirLig_radialStatus.py -d <synchronization delay in hours, default to 12 hours>")
        sys.exit(2)
        
    if not argv:
        delay = 12  # default delay in hours
    else:
        for opt, arg in opts:
            if opt == '-h':
                print("Usage: HFR-TirLig_radialStatus.py -d <synchronization delay in hours, default to 12 hours>")
                sys.exit()
            elif opt in ("-d", "--delay"):
                # Check if the delay is a valid integer
                try:
                    delay = int(arg)
                except ValueError:
                    print("Invalid delay value. Please specify a valid integer.")
                    sys.exit(2)
                
    # Create logger
    logger = logging.getLogger('HFR-TirLig_radialStatus')
    logger.setLevel(logging.INFO)
    # Create console handler and set level to DEBUG
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # Create logfile handler
    lfh = logging.FileHandler('/var/log/HFR-TirLig_radialStatus/HFR-TirLig_radialStatus.log')
    lfh.setLevel(logging.INFO)
    # Create formatter
    formatter = logging.Formatter('[%(asctime)s] -- %(levelname)s -- %(module)s - %(message)s', datefmt = '%d-%m-%Y %H:%M:%S')
    # Add formatter to lfh and ch
    lfh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # Add lfh and ch to logger
    logger.addHandler(lfh)
    logger.addHandler(ch)
    
    # Set parameter for Mysql database connection
    sqlConfig = {
      'user': 'SOCIBuserHOORT',
      'password': '!_1nM3Fu0B03huacyS_!',
      'host': '150.145.136.104',
      'database': 'HFR_node_db',
    }
    
    # Initialize error flag
    EHNerr = False

    # Set the network ID
    networkID = 'HFR-TirLig'
    
    logger.info('Processing started.')
    
#####
# Retrieval of the information about the network and the stations
#####
    
    # Create SQLAlchemy engine for connecting to database
    eng = sqlalchemy.create_engine('mysql+mysqlconnector://' + sqlConfig['user'] + ':' + \
                                   sqlConfig['password'] + '@' + sqlConfig['host'] + '/' + \
                                   sqlConfig['database'])
    
    try:
        # Set and execute the query and get the HFR network data
        networkSelectQuery = 'SELECT * FROM network_tb WHERE network_id=\'' + networkID + '\''
        networkData = pd.read_sql(networkSelectQuery, con=eng)
        logger.info(networkID + ' network data successfully fetched from EU HFR NODE database.')
        # Set and execute the query and get the active HFR station data
        if networkID == 'HFR-WesternItaly':
            stationSelectQuery = 'SELECT * FROM station_tb WHERE network_id=\'HFR-TirLig\' OR network_id=\'HFR-LaMMA\' OR network_id=\'HFR-ARPAS\' AND operational_to IS NULL'
        else:
            stationSelectQuery = 'SELECT * FROM station_tb WHERE network_id=\'' + networkID + '\' AND operational_to IS NULL'
        stationData = pd.read_sql(stationSelectQuery, con=eng)
        numStations = stationData.shape[0]
        logger.info(networkID + ' station data successfully fetched from EU HFR NODE database.')

    except sqlalchemy.exc.DBAPIError as err:        
        EHNerr = True
        logger.error('MySQL error ' + err._message())
        logger.info('Exited with errors.')
        sys.exit()

#####
# Retrieval of the information about radial delay and the number of radial files with a critically low number of velocity vectors
#####

    try:
        # Create the dataframe containing the information relevant for the alerting
        alertDF = stationData[['station_id', 'radial_QC_radial_count_threshold']].copy()

        # Get the radial delay data
        delayDF = pd.concat([getRadialDelay(row,eng,logger) for _, row in alertDF[['station_id']].iterrows()], ignore_index=True)

        # Get the radial count data
        countDF = pd.concat([getRadialCount(row,delay, eng,logger) for _, row in alertDF.iterrows()], ignore_index=True)

        # Merge the radial delay and count data into a single dataframe
        alertDF = pd.merge(alertDF, delayDF, on='station_id', how='left')
        alertDF = pd.merge(alertDF, countDF, on='station_id', how='left')

        # Remove the rows where the synchronization delay is less than the delay threshold and the number of files with enough velocity vectors is 0 (no alert is needed)
        alertDF = alertDF[~((alertDF['radial_delay'] <= delay) & (alertDF['number_of_radials_below_threshold'] == 0))].reset_index(drop=True)

#####
# Composition of the alert email
#####

        if not alertDF.empty:
            EHNerr = sendAlertEmail(alertDF,networkData,delay,logger)
        
    except Exception as err:
        EHNerr = True
        logger.error(err.args[0] + ' in getting radial delay and radial count information.')
    
####################
    
    if(not EHNerr):
        logger.info('Successfully executed.')
    else:
        logger.info('Exited with errors.')
            
####################


#####################################
# SCRIPT LAUNCHER
#####################################    
    
if __name__ == '__main__':
    main(sys.argv[1:])
    
    