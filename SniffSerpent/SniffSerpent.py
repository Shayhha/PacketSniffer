import sys
import os
import re
import logging
logging.getLogger('scapy.runtime').setLevel(logging.ERROR)
from abc import ABC, abstractmethod
import scapy.all as scapy
from scapy.all import sniff, wrpcap, rdpcap, get_if_list, IP, IPv6, TCP, UDP, ICMP, ARP, Raw 
from scapy.layers.dns import DNS
from scapy.layers.http import HTTP, HTTPRequest, HTTPResponse
from scapy.layers.dhcp import DHCP, BOOTP
from scapy.layers.tls.all import TLS, TLSClientHello, TLSServerHello, TLSClientKeyExchange, TLSServerKeyExchange, TLSNewSessionTicket
from scapy.contrib.igmp import IGMP
from scapy.layers.l2 import STP
from PyQt5.uic import loadUi
from PyQt5.QtCore import pyqtSignal, Qt, QThread, QTimer, QSize, QRegExp
from PyQt5.QtGui import QIcon, QPixmap, QStandardItem, QStandardItemModel, QRegExpValidator, QIntValidator
from PyQt5.QtWidgets import QApplication, QDesktopWidget, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy, QDialog, QLabel, QPushButton, QStyle, QHBoxLayout, QFileDialog
from urllib.parse import unquote
from queue import Queue


#------------------------------------------------------Default_Packet-------------------------------------------------------#
class Default_Packet(ABC): #abstarct class for default packet
    name = None #represents the packet name
    packet = None #represents the packet object itself for our use later
    packetType = None #represents the packet type based on scapy known types
    id = None #represents the id for the packet object, for ease of use in dictionary later

    def __init__(self, name=None, packet=None, id=None): #ctor for default packet 
        self.name = name
        self.packet = packet
        self.id = id
        

    #get method for id
    def getId(self): 
        return self.id #return the id 
    

    #set method for packet type
    def setPacketType(self, packetType): 
        self.packetType = packetType


    #get method for packet object
    def getPacket(self):
        return self.packet #return the packet object
    

    #method for raw info capture
    def rawInfo(self):
        output = ''
        if Raw in self.packet: #insert payload data (if available)
            payload = self.packet[Raw].load #get payload data from packet
            output += f'Payload Data: {payload.hex()}\n\n' #insert payload as hexadecimal
        return output
    

    #method that handles a long string and makes it fit in the GUI 
    def fitStr(self, st, info): 
        output = ''
        if info is not None: #if info not none we continue
            if isinstance(info, list): #if given info is list we convert it to utf-8 string
                info = ', '.join(item.decode('utf-8', 'replace') if isinstance(item, bytes) else str(item) for item in info) #decode the list into string
            elif isinstance(info, bytes): #if given info is byte we convert it to utf-8 string
                info = info.decode('utf-8', 'replace') #decode the byte to string
            info = info.rstrip('.') #remove trailing dot if present
            if len(info) >= 52: #if the string is longer then specified length we add a new line
                temp = '\n'.join(info[i:i+52] for i in range(0, len(info), 52)) #iterating over the string and adding new line after specified amount of characters
                output += f'{st}\n{temp}\n\n' #insert to the output 
            elif len(f'{st}: {info}') >= 52: #if the info string and st string togther exceed the specified characters we add new line
                output += f'{st}\n{info}\n\n' #insert to the output
            else: #else info and st strings are not exceeding the specifed amount of characters
                output += f'{st} {info}\n\n' #we add the original info and st strings to the output without a new line
        else: #else info is none
            output += f'{st} {info}\n\n' #add to output the value with none value 
        return output


    #method for retrieving login credentials from http packet
    def loginInfo(self):
        credentials = {} #credentials dictionary for username and password
        httpRegex = lambda key: rf'{key}=([^&]+)' #regex for http payload template, regex that ends in & at the end (if present)
        #list for usernames and password labels that are common in http payloads
        usernames = ['username', 'Username', 'UserName', 'user', 'User', 'uname', 'Uname', 'usr', 'Usr', 'email', 'Email', 'login', 'Login', 'usrname', 'Usrname', 'uid', 'Uid']
        passwords = ['password', 'Password', 'pass', 'Pass', 'pwd', 'Pwd', 'passwd', 'Passwd', 'pswd', 'psw', 'secret', 'Secret', 'secure', 'Secure', 'key', 'Key', 'auth', 'Auth']
        if self.packet.haslayer(Raw) and self.packet.haslayer(HTTPRequest): #if true we have http request packet and it has a payload
            payload = self.packet[Raw].load.decode('utf-8', 'replace') #we decode the payload of the packet 
            for username in usernames: #we iterate over the usernames to check if there's a matching username label
                if username in payload or username.upper() in payload: #if true we found a matching label
                    userRegex = httpRegex(username) #create a regex with the username label and regex template
                    usr = re.search(userRegex, payload) #we call search method of regex to check if the username matching the regex 
                    if usr: #if true the username is valid
                        credentials['username'] = unquote(usr.group(1)) #we add the username to the dictionary
                        break
            if credentials: #if we found a username, we continue to get the password
                for password in passwords:  #we iterate over the passwords to check if there's a matching password label
                    if password in payload or password.upper() in payload: #if true we found a matching label
                        passRegex = httpRegex(password) #create a regex with the password label and regex template
                        pwd = re.search(passRegex, payload) #we call search method of regex to check if the password matching the regex 
                        if pwd: #if true the password is valid
                            credentials['password'] = unquote(pwd.group(1)) #we add the password to the dictionary
                            break
        return credentials


    #method for ip configuration capture
    def ipInfo(self): 
        output = ''
        if self.packet.haslayer(IP): #if packet has ip layer
            srcIp = self.packet[IP].src #represents the source ip
            dstIp = self.packet[IP].dst #represents the destination ip
            ttl = self.packet[IP].ttl #represents ttl parameter in packet
            dscp = self.packet[IP].tos #represents dscp parameter in packet
            output += self.fitStr('Source IP:', srcIp) #insert source ip to output
            output += self.fitStr('Destination IP:', dstIp) #insert denstination ip to output
            output += f'TTL: {ttl}, DSCP: {dscp}\n\n' #add both to output
        elif self.packet.haslayer(IPv6): #if packet has ipv6 layer
            srcIp = self.packet[IPv6].src #represents the source ip
            dstIp = self.packet[IPv6].dst #represents the destination ip
            hopLimit = self.packet[IPv6].hlim #represents the hop limit parameter in packet
            trafficClass = self.packet[IPv6].tc #represnets the traffic class in packet
            output += self.fitStr('Source IP:', srcIp) #insert source ip to output
            output += self.fitStr('Destination IP:', dstIp) #insert denstination ip to output
            output += f'Hop Limit: {hopLimit}, Traffic Class: {trafficClass}\n\n' #add them both to output
        if hasattr(self.packet, 'chksum') and not self.packet.haslayer(IGMP): #if packet has checksum parameter (IGMP has its own)
            output += f'Checksum: {self.packet.chksum}\n\n' #we add the checksum to output
        output += f'Packet Size: {len(self.packet)} bytes\n\n' #add the packet size to output
        return output


    #method representing the packet briefly, derived classes may need to implement for different types
    def info(self): 
        output = '' #output string for information of packet
        srcMac = self.packet.src #represents the source mac address
        dstMac = self.packet.dst #represents the destination mac address
        srcPort = '' #source port of packet
        dstPort = '' #destination port of packet
        packetSize = len(self.packet) #size of the packet

        if self.packet.haslayer(TCP) or self.packet.haslayer(UDP): #if packet is tcp or udp we get port info
            srcPort = self.packet.sport #represents the source port of packet
            dstPort = self.packet.dport #represents the destination port of packet
            if self.packet.haslayer(IP): #if packet have ip address so we print the packet info with ip and port
                srcIp = self.packet[IP].src #represents the source ip of packet
                dstIp = self.packet[IP].dst #represents the destination ip of packet
                output += f'{self.name} Packet: ({srcIp}):({srcPort}) --> ({dstIp}):({dstPort})' #insert info to output
            elif self.packet.haslayer(IPv6): #if packet have ipv6 address so we print the packet info with ip and port
                srcIp = self.packet[IPv6].src #represents the source ip of packet
                dstIp = self.packet[IPv6].dst #represents the destination ip of packet
                output += f'{self.name} Packet: ({srcIp}):({srcPort}) --> ({dstIp}):({dstPort})' #insert info to output
            else: #else no ip layer 
                output += f'{self.name} Packet: ({srcMac}):({srcPort}) --> ({dstMac}):({dstPort})' #insert info without ip to output
        if self.packet.haslayer(HTTP) and (self.packet.haslayer(HTTPResponse) or self.packet.haslayer(HTTPRequest)): #if true packet is http
            if self.packet.haslayer(HTTPRequest) and self.loginInfo(): #if true it means we have a login request http packet (with username and password)
                output += ' Type: Login Request' #add http login request type to ouput
            else: #else its a regular request or response http packet
                output += f' Type: {"Response" if self.packet.haslayer(HTTPResponse) else "Request"}' #add http type, response or request
        if self.packet.haslayer(DHCP): #if packet is DHCP 
            output += ' Type: Discover' if self.packet[DHCP].options[0][1] == 1 else '' #add type if discover
            output += ' Type: Offer' if self.packet[DHCP].options[0][1] == 2 else '' #add type if offer
            output += ' Type: Request' if self.packet[DHCP].options[0][1] == 3 else '' #add type if request
            output += ' Type: Acknowledge' if self.packet[DHCP].options[0][1] == 5 else '' #add type if acknowledge
            output += ' Type: Release' if self.packet[DHCP].options[0][1] == 7 else '' #add type if release
            output += ' Type: Info' if self.packet[DHCP].options[0][1] == 8 else '' #add type if info
        output += f' | Size: {packetSize} bytes' #insert packet size to output
        return output


    #method that represents the packet information more deeply, for derived classes to implement further
    def moreInfo(self):
        output = '' #output string for info
        if self.packet.haslayer(TCP) or self.packet.haslayer(UDP): #if packet is tcp or udp
            output += f'{self.name} Packet:\n\n' #insert packet name to output
            output += f'Source Port: {self.packet.sport}\n\n' #insert source port to output
            output += f'Destination Port: {self.packet.dport}\n\n' #insert destination port to output
        else: #else its other packet type
            output += f'{self.name} Packet:\n\n' #insert packet name to output
            output += f'Source MAC: {self.packet.src}\n\n' #insert packet source mac address
            output += f'Destination MAC: {self.packet.dst}\n\n' #insert packet destination mac address
        output += self.ipInfo() #call ip method to add neccessary info if ip layer is present
        return output

#----------------------------------------------------Default_Packet-END-----------------------------------------------------#

#-----------------------------------------------------------TCP-------------------------------------------------------------#
class TCP_Packet(Default_Packet):
    def __init__(self, packet=None, id=None): #ctor for tcp packet
        super().__init__('TCP', packet, id) #call parent ctor
        if packet.haslayer(TCP): #checks if packet is TCP
            self.packetType = TCP #specify the packet type


    #method for packet information
    def moreInfo(self): 
        output = f'{super().moreInfo()}' #call parent moreInfo method
        #prints TCP flags
        flags = self.packet[self.packetType].flags #tcp has flags, we extract the binary number that represents the flags
        flagsDict = { #we add to a dictionary all the flags of tcp
            'FIN': (flags & 0x01) != 0, #we extract FIN flag with '&' operator with 0x01(0001 in binary)
            'SYN': (flags & 0x02) != 0, #we extract SYS flag with '&' operator with 0x02(0010 in binary)
            'RST': (flags & 0x04) != 0, #we extract RST flag with '&' operator with 0x04(0100 in binary)
            'PSH': (flags & 0x08) != 0, #we extract PSH flag with '&' operator with 0x08(1000 in binary)
            'ACK': (flags & 0x10) != 0, #we extract ACK flag with '&' operator with 0x10(0001 0000 in binary)
            'URG': (flags & 0x20) != 0, #we extract URG flag with '&' operator with 0x20(0010 0000 in binary)
        }

        output += f'Sequence Number: {self.packet.seq}\n\n' #add the sequence number to output
        output += f'Acknowledgment Number: {self.packet.ack}\n\n' #add the acknowledgment number to output
        output += f'Window Size: {self.packet.window} bytes\n\n' #add window size parameter to output
        output += 'Flags:\n' #add the flags to output
        temp = '' #temp string for our use 
        for flag, value in flagsDict.items(): #iteration over the flags in tcp packet
            if flag == 'ACK': #if flag is ACK we add new line for clean gui representation
                temp += '\n' #add new line to temp
            temp += f'{flag}: {value}, ' #add the current flag with its value
        output += temp.rstrip(', ') #finally insert the flags to output 
        output += '\n\n'
        if self.packet[self.packetType].options: #add TCP Options (if available)
            output += 'TCP Options:\n' #insert the tcp options to output
            temp = '' #initializing temp to an empty string
            for option in self.packet[self.packetType].options: #iteration over the options list
                temp += f'{option[0]}: {option[1]}, ' #add the options to temp
            output += temp.rstrip(', ') #strip the output for leading comma
            output += '\n\n'
        return output

#---------------------------------------------------------TCP-END-----------------------------------------------------------#

#-----------------------------------------------------------UDP-------------------------------------------------------------#
class UDP_Packet(Default_Packet):
    def __init__(self, packet=None, id=None): #ctor 
        super().__init__('UDP', packet, id) #call parent ctor
        if packet.haslayer(UDP): #checks if packet is UDP
            self.packetType = UDP #add packet type


#---------------------------------------------------------UDP-END-----------------------------------------------------------#

#-----------------------------------------------------------HTTP------------------------------------------------------------#
class HTTP_Packet(Default_Packet):
    def __init__(self, packet=None, id=None):
        super().__init__('HTTP', packet, id) # call parent ctor
        if packet.haslayer(HTTP): #checks if packet is HTTP
            self.packetType = HTTP #add packet type


    #method for packet information
    def moreInfo(self):
        output = super().moreInfo() #call parent moreInfo method
        if self.packet.haslayer(HTTP): #if packet has HTTP layer
            httpPacket = self.packet[HTTP] #set the http packet
            headers = {} #set headers to be an empty dictionary
            if self.packet.haslayer(HTTPResponse): #if packet is http response
                httpPacket = self.packet[HTTPResponse] #set the packet as http response
            elif self.packet.haslayer(HTTPRequest): #if packet is http request
                httpPacket = self.packet[HTTPRequest] #set the packet as http request
            
            if httpPacket.haslayer(HTTPResponse) or httpPacket.haslayer(HTTPRequest): #if http packets is response or request
                for field in httpPacket.fields_desc: #iterating over fields desc list to retrive the headers dictionary
                    fieldName = field.name #field name of packet
                    fieldValue = getattr(httpPacket, fieldName) #field value of packet
                    if isinstance(fieldValue, bytes): #if field value is byte we decode it
                        fieldValue = fieldValue.decode() #decode field name byte
                    headers[fieldName] = fieldValue #finally we add field value to headers dictionary

            if self.packet.haslayer(HTTPResponse): #if the packet is response
                httpVersion = headers.get('Http_Version') #get the http version of packet
                statusCode = httpPacket.Status_Code.decode() #get the status code of response packet
                contentLength = headers.get('Content_Length') #get the content length of response packet
                server = headers.get('Server') #get the server of response packet
                output += 'Type: Response\n\n' #add type of packet to output
                output += f'HTTP Version: {httpVersion}\n\n' #add http version to output
                output += f'Status Code: {statusCode}\n\n' #add status code to output
                output += f'Content Length: {contentLength} bytes\n\n' #add content length to output
                output += self.fitStr('Server:', server) #add server of packet to output

            elif self.packet.haslayer(HTTPRequest): #if the packet is request
                httpLogin = self.loginInfo() #call loginInfo method to get login credentials (if available)
                httpVersion = headers.get('Http_Version') #get the http version of packet
                method = httpPacket.Method.decode() #get the method name of request packet
                url = httpPacket.Host.decode() + httpPacket.Path.decode() #get the url of the request packet
                accept = headers.get('Accept') #get the accept info of request
                referer = headers.get('Referer') #get the referer of request
                output += 'Type: Login Request\n\n' if httpLogin else 'Type: Request\n\n' #add type of packet to output based on http info
                output += f'HTTP Version: {httpVersion}\n\n' #add http version to output
                output += f'Method: {method}\n\n' #add method to output
                output += self.fitStr('URL:', url) #add url to output
                if httpLogin: #if true we have captured login information
                    output += 'Login Credentials:\n\n' #add login credentials to output
                    output += self.fitStr('Username:', httpLogin['username']) #add usernname from our httpLogin dict
                    output += self.fitStr('Password:', httpLogin['password']) #add password from our httpLogin dict
                output += self.fitStr('Accept:', accept) #add accept to output
                output += self.fitStr('Referer:', referer) #add referer to output
        return output
    
#---------------------------------------------------------HTTP-END----------------------------------------------------------#

#-----------------------------------------------------------DNS-------------------------------------------------------------#
class DNS_Packet(Default_Packet):
    DNSRecordTypes = {
        1: 'A', 28: 'AAAA', 18: 'AFSDB', 42: 'APL', 257: 'CAA', 60: 'CDNSKEY', 59: 'CDS', 37: 'CERT', 5: 'CNAME', 62: 'CSYNC',
        49: 'DHCID', 32769: 'DLV', 39: 'DNAME', 48: 'DNSKEY', 43: 'DS', 108: 'EUI48', 109: 'EUI64', 13: 'HINFO', 55: 'HIP',
        65: 'HTTPS', 45: 'IPSECKEY', 25: 'KEY', 36: 'KX', 29: 'LOC', 15: 'MX', 35: 'NAPTR', 2: 'NS', 47: 'NSEC', 50: 'NSEC3',
        51: 'NSEC3PARAM', 61: 'OPENPGPKEY', 12: 'PTR', 17: 'RP', 46: 'RRSIG', 24: 'SIG', 53: 'SMIMEA', 6: 'SOA', 33: 'SRV',
        44: 'SSHFP', 64: 'SVCB', 32768: 'TA', 249: 'TKEY', 52: 'TLSA', 250: 'TSIG', 16: 'TXT', 256: 'URI', 63: 'ZONEMD', 255: 'ANY'}
    
    DNSClassTypes = {1: 'IN', 2: 'CS', 3: 'CH', 4: 'HS', 255: 'ANY', 254: 'NONE', 32769: 'DLV'}

    def __init__(self, packet=None, id=None):
        super().__init__('DNS', packet, id) #call parent ctor
        if packet.haslayer(DNS): #checks if packet is DNS
            self.packetType = DNS #add packet type


    #method for brief packet information
    def info(self):
        output = '' #output string for information of packet
        dnsPacket = self.packet[DNS] #parameter for dns packet
        srcMac = self.packet.src #representst the source mac address
        dstMac = self.packet.dst #represents the destination mac address
        srcIp = '' #represents the source ip address
        dstIp = '' #represents the destination ip address
        srcPort = '' #represents the source port
        dstPort = '' #represents the destination port
        packetSize = len(self.packet) #represenets the packet size

        if self.packet.haslayer(TCP) or self.packet.haslayer(UDP): #if dns packet transmitted through tcp or udp 
            srcPort = self.packet.sport #set the source port
            dstPort = self.packet.dport #set the destination port
            if self.packet.haslayer(IP): #if packet has ip layer
                srcIp = self.packet[IP].src #set the source ip
                dstIp = self.packet[IP].dst #set the destination ip
                output += f'{self.name} Packet: ({srcIp}):({srcPort}) --> ({dstIp}):({dstPort})' #add the info with ip to output
            elif self.packet.haslayer(IPv6): #else packet has ipv6 layer
                srcIp = self.packet[IPv6].src #set the source ip
                dstIp = self.packet[IPv6].dst #set the destination ip
                output += f'{self.name} Packet: ({srcIp}):({srcPort}) --> ({dstIp}):({dstPort})' #add the info with ip to output
            else: #else no ip layer 
                output += f'{self.name} Packet: ({srcMac}):({srcPort}) --> ({dstMac}):({dstPort})' #insert info without ip to output

        output += f' Type: {"Response" if dnsPacket.qr else "Request"}' #add the dns type, response or request
        
        if dnsPacket.an: #check if its response packet
            dnsResponseType = self.DNSRecordTypes[dnsPacket.an.type] if dnsPacket.an.type in self.DNSRecordTypes else dnsPacket.an.type #represents dns record type based on the DNSRecordTypes dictionary
            output += f' {dnsResponseType}' #add response record type
        elif dnsPacket.qd: #else we check if its request packet
            dnsRequestType = self.DNSRecordTypes[dnsPacket.qd.qtype] if dnsPacket.qd.qtype in self.DNSRecordTypes else dnsPacket.qd.qtype #represents dns record type based on the DNSRecordTypes dictionary
            output += f' {dnsRequestType}' #add request record type
            
        output += f' | Size: {packetSize} bytes' #add the size of the packet
        return output


    #method for packet information
    def moreInfo(self):
        output = super().moreInfo() #call parent moreInfo method
        if self.packet.haslayer(DNS): #if packet has DNS layer
            dnsPacket = self.packet[DNS] #save the dns packet in parameter
            output += f'ID: {dnsPacket.id}\n\n' #id of the dns packet
            if dnsPacket.qr == 1: #means its a response packet
                if dnsPacket.an: #if dns packet is response packet
                    dnsResponseType = self.DNSRecordTypes[dnsPacket.an.type] if dnsPacket.an.type in self.DNSRecordTypes else dnsPacket.an.type #represents dns record type based on the DNSRecordTypes dictionary
                    dnsResponseClass = self.DNSClassTypes[dnsPacket.an.rclass] if dnsPacket.an.rclass in self.DNSClassTypes else dnsPacket.an.rclass #represents dns class type based on the DNSClassTypes dictionary
                    output += f'Type: Response\n\n' #add type of packet to output
                    output += self.fitStr('Response Name:', dnsPacket.an.rrname) #add repsonse name to output
                    output += f'Response Type: {dnsResponseType}, ' #add response type to output
                    output += f'Response Class: {dnsResponseClass}\n\n' #add response class to output
                    output += f'Num Responses: {len(dnsPacket.an)}\n\n' #add number of responses to output
                    if hasattr(dnsPacket.an, 'rdata'): #check if rdata attribute exists
                        output += self.fitStr('Response Data:', dnsPacket.an.rdata) #specify the rdata parameter
            else: #means its a request packet
                if dnsPacket.qd:
                    dnsRequestType = self.DNSRecordTypes[dnsPacket.qd.qtype] if dnsPacket.qd.qtype in self.DNSRecordTypes else dnsPacket.qd.qtype #represents dns record type based on the DNSRecordTypes dictionary
                    dnsRequestClass = self.DNSClassTypes[dnsPacket.qd.qclass] if dnsPacket.qd.qclass in self.DNSClassTypes else dnsPacket.qd.qclass #represents dns class type based on the DNSClassTypes dictionary
                    output += f'Type: Request\n\n' #add type of packet to output
                    output += self.fitStr('Request Name:', dnsPacket.qd.qname) #add request name to output
                    output += f'Request Type: {dnsRequestType}, ' #add request type to output
                    output += f'Request Class: {dnsRequestClass}\n\n' #add request class to output
                    output += f'Num Requests: {len(dnsPacket.qd)}\n\n' #add num of requests to output
        return output
    
#---------------------------------------------------------DNS-END-----------------------------------------------------------#

#-----------------------------------------------------------TLS-------------------------------------------------------------#
class TLS_Packet(Default_Packet):
    def __init__(self, packet=None, id=None):
        super().__init__('TLS', packet, id) #call parent ctor
        if packet.haslayer(TLS): #checks if packet is TLS
            self.packetType = TLS #add packet type
    
    
    #method for packet information
    def moreInfo(self):
        output = super().moreInfo() #call parent moreInfo method
        if self.packet.haslayer(TLS): #if packet has TLS layer
            tlsPacket = self.packet[TLS] #save the TLS packet in parameter
            output += f'Version: {tlsPacket.version}\n\n' #version of the TLS packet
            if self.packet.haslayer(TLSClientHello): #if true the packet is a client hello response
                output += f'Handshake Type: Client Hello\n\n' #add handshake type to output
                output += f'Length: {self.packet[TLSClientHello].msglen} bytes\n\n' #add length to output
                output += self.fitStr('Cipher Suites:', self.packet[TLSClientHello].ciphers) #add cipher suites list to output
            elif self.packet.haslayer(TLSServerHello): #if true the packet is a server hello response
                output += f'Handshake Type: Server Hello\n\n' #add handshake tyoe to output
                output += f'Length: {self.packet[TLSServerHello].msglen} bytes\n\n' #add length to output
                output += f'Cipher Suite: {self.packet[TLSServerHello].cipher}\n\n' #add cipher suite number to output
            elif self.packet.haslayer(TLSClientKeyExchange): #if true the packet is a client key exchange response
                output += f'Handshake Type: Client Key Exchange\n\n' #add handshake tyoe to output
                output += f'Length: {self.packet[TLSClientKeyExchange].msglen} bytes\n\n' #add length to output
            elif self.packet.haslayer(TLSServerKeyExchange): #if true the packet is a server key exchange response
                output += f'Handshake Type: Server Key Exchange\n\n' #add handshake tyoe to output
                output += f'Length: {self.packet[TLSServerKeyExchange].msglen} bytes\n\n' #add length to output
            elif self.packet.haslayer(TLSNewSessionTicket): #if true the packet is a new session ticket response
                output += f'Handshake Type: New Session Ticket\n\n' #add handshake tyoe to output
                output += f'Length: {self.packet[TLSNewSessionTicket].msglen} bytes\n\n' #add length to output
        return output
    
#---------------------------------------------------------TLS-END-----------------------------------------------------------#

#-----------------------------------------------------------ICMP------------------------------------------------------------#
class ICMP_Packet(Default_Packet):
    icmpTypes = { 
        0: 'Echo Reply', 3: 'Destination Unreachable', 4: 'Source Quench', 5: 'Redirect', 8: 'Echo Request', 9: 'Router Advertisement',
        10: 'Router Selection', 11: 'Time Exceeded', 12: 'Parameter Problem', 13: 'Timestamp', 14: 'Timestamp Reply', 15: 'Information Request',
        16: 'Information Reply', 17: 'Address Mask Request', 18: 'Address Mask Reply'}
    
    def __init__(self, packet=None, id=None):
        super().__init__('ICMP', packet, id) #call parent ctor
        if packet.haslayer(ICMP): #checks if packet is icmp
            self.packetType = ICMP #add packet type

    
    #method for brief packet information
    def info(self):
        output = ''
        packetSize = len(self.packet) #represent the packet size
        icmpType = self.icmpTypes[self.packet[ICMP].type] if self.packet[ICMP].type in self.icmpTypes else self.packet[ICMP].type #represents icmp type based on the icmpTypes dictionary
        icmpCode = self.packet[ICMP].code #represents icmp code
        if self.packet.haslayer(IP): #if packet has ip layer
            srcIp = self.packet[IP].src #represents the source ip
            dstIp = self.packet[IP].dst #represents the destination ip
            output += f'{self.name} Packet: ({srcIp}) --> ({dstIp}) | Type: {icmpType}, Code: {icmpCode} | Size: {packetSize} bytes' #add to output the packet info with ip
        elif self.packet.haslayer(IPv6): #if packet has ipv6 layer
            srcIp = self.packet[IPv6].src #represents the source ip
            dstIp = self.packet[IPv6].dst #represents the destination ip
            output += f'{self.name} Packet: ({srcIp}) --> ({dstIp}) | Type: {icmpType}, Code: {icmpCode} | Size: {packetSize} bytes' #add to output the packet info with ip
        else:
            output += f'{self.name} Packet: Type: {icmpType}, Code: {icmpCode} | Size: {packetSize} bytes' #add to output the packet info 
        return output


    #method for packet information
    def moreInfo(self): 
        output = ''
        if self.packet.haslayer(ICMP): #if packet has icmp layer
            icmpType = self.icmpTypes[self.packet[ICMP].type] if self.packet[ICMP].type in self.icmpTypes else self.packet[ICMP].type #represents icmp type based on the icmpTypes dictionary
            icmpCode = self.packet[ICMP].code #represents icmp code
            icmpSeq = self.packet[ICMP].seq #represents icmp sequence number
            icmpId = self.packet[ICMP].id #represents icmp identifier
            output += f'{self.name} Packet:\n\n' #add packet name to output
            output += self.ipInfo() #call ip method for more ip info
            output += f'Type: {icmpType}\n\n' #add icmp type to output
            output += f'Code: {icmpCode}\n\n' #add icmp code to output
            output += f'Sequence Number: {icmpSeq}\n\n' #add icmp sequence number
            output += f'Identifier: {icmpId}\n\n' #add icmp identifier
        return output

#---------------------------------------------------------ICMP-END----------------------------------------------------------#

#-----------------------------------------------------------DHCP------------------------------------------------------------#
class DHCP_Packet(Default_Packet):
    def __init__(self, packet=None, id=None):
        super().__init__('DHCP', packet, id) #call parent ctor
        if packet.haslayer(DHCP): #if packet is DHCP
            self.packetType = DHCP #set packet type
        
    
    #method to retreive the option from the options list in DHCP packet
    def getOption(self, parameter):
        byteParameters = ['hostname', 'vendor_class_id', 'client_id'] #list that includes parameters to decode
        for option in self.packet[DHCP].options: #if true the packet is DHCP
            if option[0] == parameter: # if true we found a valid parameter in the list
                if parameter == 'name_server' and len(option) > 2: #if DHCP returned multiple name servers 
                    return ", ".join(option[1:]) #return all names with a comma seperating them
                elif parameter in byteParameters: #if parameter in byteParameter list
                    return option[1].decode() #we return the decoded parameter
                else: #else we return the parameter in the list
                    return option[1] #return the value in the tuple in list
        return None #else we return none if parameter is'nt in the list
                    

    #method for packet information
    def moreInfo(self):
        output = super().moreInfo() #call parent moreInfo method
        if self.packet.haslayer(DHCP): #if true its a DHCP packet
            dhcpPacket = self.packet[DHCP] #set the DHCP packet in variable
            if dhcpPacket.options[0][1] == 1 or dhcpPacket.options[0][1] == 3: #if true its a dicovery/request DHCP packet
                hostname = self.getOption('hostname') #get the hostname from options
                serverID = self.getOption('server_id') #get the server id from options
                requestedAddress = self.getOption('requested_addr') #get the requested address from options
                vendorClassID = self.getOption('vendor_class_id') #get vendor class id from options
                paramReqList = self.getOption('param_req_list') #get parameter request list from options
                output += f'DHCP Type: Discover\n\n' if dhcpPacket.options[0][1] == 1 else f'DHCP Type: Request\n\n' #add type of DHCP, discovery or request
                output += f'Host Name: {hostname}\n\n' if hostname else '' #add hostname to output
                output += f'Server ID: {serverID}\n\n' if dhcpPacket.options[0][1] == 3 and serverID else '' #add server id to output
                output += f'Requested Address: {requestedAddress}\n\n' if requestedAddress else '' #add requested addresses to outpit
                output += f'Vendor Class ID: {vendorClassID}\n\n' if vendorClassID else '' #add vendor class id to output
                output += self.fitStr('Parameter Request list:', ', '.join(map(str, paramReqList))) if paramReqList else '' #add parameter request list to output
            elif dhcpPacket.options[0][1] == 2 or dhcpPacket.options[0][1] == 5: #if true its a offer/aknowledge DHCP packet
                subnetMask = self.getOption('subnet_mask') #get subnet mask from options
                broadcastAddress = self.getOption('broadcast_address') #get boradcast address from options
                leaseTime = self.getOption('lease_time') #get lease time from options
                router = self.getOption('router') #get router from options
                serverName = self.getOption('name_server') #get server name from options
                output += f'DHCP Type: Offer\n\n' if dhcpPacket.options[0][1] == 2 else f'DHCP Type: Acknowledge\n\n' #add type of DHCP, offer or acknowledge
                output += f'Subnet Mask: {subnetMask}\n\n' if subnetMask else '' #add subnet mask to output
                output += f'Broadcast Address: {broadcastAddress}\n\n' if broadcastAddress else '' #add broadcast address to output
                output += f'Lease Time: {leaseTime}\n\n' if leaseTime else '' #add lease time to output
                output += f'Router Address: {router}\n\n' if router else '' #add router address to output
                output += f'Offered Address: {self.packet[BOOTP].yiaddr}\n\n' if dhcpPacket.options[0][1] == 2 else f'Acknowledged Address: {self.packet[BOOTP].yiaddr}\n\n' #add specific info about the packet
                output += self.fitStr('Server Name:', serverName) if serverName else '' #add server name to output
            elif dhcpPacket.options[0][1] == 7: #if true its a release DHCP packet
                serverID = self.getOption('server_id') #get server id from options
                output += f'DHCP Type: Release\n\n' #add type to output
                output += f'Server ID: {serverID}\n\n' if serverID else '' #add server id to output
            elif dhcpPacket.options[0][1] == 8: #if true its a information DHCP packet
                hostname = self.getOption('hostname') #get hostname from output
                vendorClassID = self.getOption('vendor_class_id') #get vendor class id from options
                output += f'DHCP Type: Information\n\n' #add type to output
                output += f'Host Name: {hostname}\n\n' if hostname else '' #add hostname to output
                output += f'Vendor Class ID: {vendorClassID}\n\n' if vendorClassID else '' #add vendor class id to output
        return output
    
#----------------------------------------------------------DHCP-END---------------------------------------------------------#

# -----------------------------------------------------------ARP------------------------------------------------------------#
class ARP_Packet(Default_Packet):
    hardwareTypes = {
        1: 'Ethernet', 4: 'Ethernet II', 6: 'IEEE 802 (Token Ring)', 8: 'ArcNet', 15: 'Frame Relay', 17: 'ATM',
        18: 'HDLC', 23: 'IEEE 802.11 (Wi-Fi)', 32: 'Fibre Channel', 41: 'InfiniBand', 42: 'IPv6 over Ethernet', 512: 'PPP'}

    protocolTypes = {
        1: 'Ethernet', 2045: 'VLAN Tagging (802.1Q)', 2046: 'RARP', 2048: 'IPv4', 2049: 'X.25', 2054: 'ARP', 32902: 'RARP', 33058: 'AppleTalk (Appletalk AARP)', 
        33079: 'AppleTalk', 34304: 'PPP', 4525: 'IPv6', 34887: 'PPPoE Discovery', 35020: 'MPLS', 35023: 'PPPoE (PPP over Ethernet)', 35048: 'MPLS Multicast', 35117: 'PPPoE Session'}

    def __init__(self, packet=None, id=None):
        super().__init__('ARP', packet, id) #call parent ctor
        if packet.haslayer(ARP): #checks if packet is arp
            self.packetType = ARP #add packet type
    

    #method for brief packet information
    def info(self):
        output = ''
        srcMac = self.packet[ARP].hwsrc #represents arp source mac address
        srcIp = self.packet[ARP].psrc #represents arp source ip address
        dstMac = self.packet[ARP].hwdst #represents arp destination mac address
        dstIp = self.packet[ARP].pdst #represents arp destination ip address
        arpOperation = 'Request' if self.packet[ARP].op == 1 else 'Reply' #represents arp operation
        packetSize = len(self.packet) #represents the packet size 
        output += f'{self.name} Packet: ({srcIp}):({srcMac}) --> ({dstIp}):({dstMac}) Type: {arpOperation} | Size: {packetSize} bytes' #add the packet info to output
        return output


    #method for packet information
    def moreInfo(self):
        output = ''
        if self.packet.haslayer(ARP): #if packet has layer of arp
            hardwareType = self.hardwareTypes[self.packet[ARP].hwtype] if self.packet[ARP].hwtype in self.hardwareTypes else self.packet[ARP].hwtype #represents hardware type based on the hardwareTypes dictionary
            protocolType = self.protocolTypes[self.packet[ARP].ptype] if self.packet[ARP].ptype in self.protocolTypes else self.packet[ARP].ptype #represents protocol type based on the protocolTypes dictionary
            output += f'{self.name} Packet:\n\n' #add packet name to output
            output += f'Source MAC: {self.packet[ARP].hwsrc}\n\n' #add arp source mac address
            output += f'Destination MAC: {self.packet[ARP].hwdst}\n\n' #add arp destination mac address
            output += f'Source IP: {self.packet[ARP].psrc}\n\n' #add arp source ip address
            output += f'Destination IP: {self.packet[ARP].pdst}\n\n' #add arp destination ip address
            output += f'Packet Size: {len(self.packet)} bytes\n\n' #add packet size
            output += f'Operation: {"Request" if self.packet[ARP].op == 1 else "Reply"}\n\n' #add the arp operation to output
            output += f'Hardware Type: {hardwareType}\n\n' #add the hardware type to output
            output += f'Hardware Length: {self.packet[ARP].hwlen} bytes\n\n' #add hardware length to output
            output += f'Protocol Type: {protocolType}\n\n' #add protocol type to output
            output += f'Protocol Length: {self.packet[ARP].plen} bytes\n\n' #add protocol length to output
        return output
        
#-----------------------------------------------------------ARP-END---------------------------------------------------------#

#-----------------------------------------------------------IGMP------------------------------------------------------------#
class IGMP_Packet(Default_Packet):
    igmpTypes = {
        17: 'Membership Query', 18: 'Membership Report v1', 22: 'Membership Report v2', 23: 'Leave Group', 30: 'Membership Report v3',
        31: 'Multicast Router Advertisement', 32: 'Multicast Router Solicitation', 33: 'Multicast Router Termination'}

    def __init__(self, packet=None, id=None):
        super().__init__('IGMP', packet, id) #call parent ctor
        if packet.haslayer(IGMP): #checks if packet is IGMP
            self.packetType = IGMP #add pacet type
            

    #method for brief packet information
    def info(self):
        output = ''
        srcMac = self.packet.src #represents the source mac address
        dstMac = self.packet.dst #represents the destination mac address
        packetSize = len(self.packet) #size of the packet
        igmpType = self.igmpTypes[self.packet[IGMP].type] #represents the igmp type
        if self.packet.haslayer(IP): #if packet have ip address so we add the packet info with ip and type
            srcIp = self.packet[IP].src #represents the source ip of packet
            dstIp = self.packet[IP].dst #represents the destination ip of packet
            output += f'{self.name} Packet: ({srcIp}) --> ({dstIp}) Type: {igmpType} | Size: {packetSize} bytes' #insert info to output
        elif self.packet.haslayer(IPv6):  #if packet have ipv6 address so we add the packet info with ip and type
            srcIp = self.packet[IPv6].src #set the source ip
            dstIp = self.packet[IPv6].dst #set the destination ip
            output += f'{self.name} Packet: ({srcIp}) --> ({dstIp}) Type: {igmpType} | Size: {packetSize} bytes' #insert info to output
        else: #if packet doesnt have ip layer we print its mac address annd type
            output += f'{self.name} Packet: ({srcMac}) --> ({dstMac}) Type: {igmpType} | Size: {packetSize} bytes' #insert info to output
        return output   


    #method for packet information
    def moreInfo(self):
        output = super().moreInfo() #call parent moreInfo
        if self.packet.haslayer(IGMP): #if true it means packet is IGMP
            igmpType = self.igmpTypes[self.packet[IGMP].type] if self.packet[IGMP].type in self.igmpTypes else self.packet[IGMP].type #represents IGMP type based on the igmpTypes dictionary
            output += f'Type: {igmpType}\n\n' #add IGMP type to output
            output += f'Group Address: {self.packet[IGMP].gaddr}\n\n' #add IGMP group address to output
            output += f'Maximum Response Code: {self.packet[IGMP].mrcode}\n\n' #add IGMP mrcode to output
            output += f'Checksum: {self.packet[IGMP].chksum}\n\n' #add IGMP checksum to output
        return output

#---------------------------------------------------------IGMP-END----------------------------------------------------------#

#-----------------------------------------------------------STP-------------------------------------------------------------#
class STP_Packet(Default_Packet):
    def __init__(self, packet=None, id=None):
        super().__init__('STP', packet, id) #call parent ctor
        if packet.haslayer(STP): #checks if packet is stp
            self.packetType = STP #add pacet type


    #method for brief packet information
    def info(self):
        output = ''
        packetSize = len(self.packet) #represents the stp packet size
        output += f'{self.name} Packet: ({self.packet.src}) --> ({self.packet.dst}) | Size: {packetSize} bytes' #add packet info to output
        return output

    
    #method for packet information
    def moreInfo(self):
        output = ''
        if self.packet.haslayer(STP): #if packet is an stp packet
            stpProto = self.packet[STP].proto #represents stp protocol
            stpVersion = self.packet[STP].version #represents stp version
            stpBridgeId = self.packet[STP].bridgeid #represents stp bridge id
            stpPortId = self.packet[STP].portid #represents stp port id
            stpPathCost = self.packet[STP].pathcost #represents stp path cost
            stpAge = self.packet[STP].age #represents stp age
            output += f'{self.name} Packet:\n\n' #add packet name to output
            output += f'STP Protocol: {stpProto}\n\n' #add stp protocol to output
            output += f'Version: {stpVersion}\n\n' #add stp version to output
            output += f'Source MAC: {self.packet.src}\n\n' #add source mac address to output
            output += f'Destination MAC: {self.packet.dst}\n\n' #add destination mac address to output
            output += f'Bridge ID: {stpBridgeId}\n\n' #add bridge id tto output
            output += f'Port ID: {stpPortId}\n\n' #add port id to output
            output += f'Path Cost: {stpPathCost}\n\n' #add path cost to output
            output += f'Age: {stpAge}\n\n' #add stp age to output
        output += f'Packet Size: {len(self.packet)} bytes\n\n' #add packet size to output
        return output

# ---------------------------------------------------------STP-END----------------------------------------------------------#

#----------------------------------------------------HELPER-FUNCTIONS-------------------------------------------------------#

#method to print all available interfaces
def getAvailableInterfaces():
    #get a list of all available network interfaces
    interfaces = get_if_list() #call get_if_list method to retrieve the available interfaces
    if interfaces: #if there are interfaces we print them
        print('Available network interfaces:')
        i = 1 #counter for the interfaces 
        for interface in interfaces: #print all availabe interfaces
            if sys.platform.startswith('win32'): #if ran on windows we convert the guid number
                print(f'{i}. {guidToStr(interface)}')
            else: #else we are on other os so we print the interface 
                print(f'{i}. {interface}')
            i += 1
    else: #else no interfaces were found
        print('No network interfaces found.')


#method for retrieving interface name from GUID number (Windows only)
def guidToStr(guid):
    try: #we try to import the specific windows method from scapy library
        from scapy.arch.windows import get_windows_if_list
    except ImportError as e: #we catch an import error if occurred
        print(f'Error importing module: {e}') #print the error
        return guid #we exit the function
    interfaces = get_windows_if_list() #use the windows method to get list of guid number interfaces
    for interface in interfaces: #iterating over the list of interfaces
        if interface['guid'] == guid: #we find the matching guid number interface
            return interface['name'] #return the name of the interface associated with guid number
    return guid #else we didnt find the guid number so we return given guid


#method for retrieving the network interfaces
def getNetworkInterfaces():
    networkNames = ['eth', 'wlan', 'en', 'enp', 'wlp', 'lo', 'Ethernet', 'Wi-Fi', '\\Device\\NPF_Loopback'] #this list represents the usual network interfaces that are available in various platfroms
    interfaces = get_if_list() #get a list of the network interfaces
    if sys.platform.startswith('win32'): #if current os is Windows we convert the guid number to interface name
        interfaces = [guidToStr(interface) for interface in interfaces] #get a new list of network interfaces with correct names instead of guid numbers
    matchedInterfaces = [interface for interface in interfaces if any(interface.startswith(name) for name in networkNames)] #we filter the list to retrieving ethernet and wifi interfaces
    return matchedInterfaces #return the matched interfaces as list

#-----------------------------------------------------HANDLE-FUNCTIONS------------------------------------------------------#
#method that handles TCP packets
def handleTCP(packet):
    global packetCounter
    TCP_Object = TCP_Packet(packet, packetCounter) #create a new object for packet
    packetDictionary[TCP_Object.getId()] = TCP_Object #insert it to packet dictionary
    packetCounter += 1 #increase the counter
    return TCP_Object #finally return the object

#method that handles UDP packets
def handleUDP(packet):
    global packetCounter
    UDP_Object = UDP_Packet(packet, packetCounter) #create a new object for packet
    packetDictionary[UDP_Object.getId()] = UDP_Object #insert it to packet dictionary
    packetCounter += 1 #increase the counter
    return UDP_Object #finally return the object

#method that handles HTTP packets
def handleHTTP(packet):
    global packetCounter
    HTTP_Object = HTTP_Packet(packet, packetCounter) #create a new object for packet
    packetDictionary[HTTP_Object.getId()] = HTTP_Object #insert it to packet dictionary
    packetCounter += 1 #increase the counter
    return HTTP_Object #finally return the object

#method that handles DNS packets
def handleDNS(packet):
    global packetCounter
    DNS_Object = DNS_Packet(packet, packetCounter) #create a new object for packet
    packetDictionary[DNS_Object.getId()] = DNS_Object #insert it to packet dictionary
    packetCounter += 1 #increase the counter
    return DNS_Object #finally return the object

#method that handles TLS packets
def handleTLS(packet):
    global packetCounter
    if packet[TLS].type == 22: #we need to capture handshakes TLS packets so 22 is the correct type
        TLS_Object = TLS_Packet(packet, packetCounter) #create a new object for packet
        packetDictionary[TLS_Object.getId()] = TLS_Object #insert it to packet dictionary
        packetCounter += 1 #increase the counter
        return TLS_Object #finally return the object
    return None #else we return none

#method that handles ICMP packets
def handleICMP(packet):
    global packetCounter 
    ICMP_Object = ICMP_Packet(packet, packetCounter) #create a new object for packet
    packetDictionary[ICMP_Object.getId()] = ICMP_Object #insert it to packet dictionary
    packetCounter += 1 #increase the counter
    return ICMP_Object #finally return the object

#method that handles DHCP packets
def handleDHCP(packet):
    global packetCounter
    validParameters = [1, 2, 3, 5, 7, 8] #list that represents the valid paramteters for DHCP
    if packet[DHCP].options[0][1] in validParameters: #we check if its a valid parameter
        DHCP_Object = DHCP_Packet(packet, packetCounter) #create a new object for packet
        packetDictionary[DHCP_Object.getId()] = DHCP_Object #insert it to packet dictionary
        packetCounter += 1 #increase the counter
        return DHCP_Object #finally return the object
    return None #else we return none

#method that handles ARP packets
def handleARP(packet):
    global packetCounter
    ARP_Object = ARP_Packet(packet, packetCounter) #create a new object for packet
    packetDictionary[ARP_Object.getId()] = ARP_Object #insert it to packet dictionary
    packetCounter += 1 #increase the counter
    return ARP_Object #finally return the object

#method that handles IGMP packets
def handleIGMP(packet):
    global packetCounter
    validParameters = [17, 18, 22, 23] #list that represents the valid paramteters for IGMP
    if packet[IGMP].type in validParameters: #we check if its a valid parameter
        IGMP_Object = IGMP_Packet(packet, packetCounter) #create a new object for packet
        packetDictionary[IGMP_Object.getId()] = IGMP_Object #insert it to packet dictionary
        packetCounter += 1 #increase the counter
        return IGMP_Object #finally return the object
    return None #else we return none

#method that handles STP packets
def handleSTP(packet):
    global packetCounter
    STP_Object = STP_Packet(packet, packetCounter) #create a new object for packet
    packetDictionary[STP_Object.getId()] = STP_Object #insert it to packet dictionary
    packetCounter += 1 #increase the counter
    return STP_Object #finally return the object

#---------------------------------------------------HANDLE-FUNCTIONS-END----------------------------------------------------#

packetDictionary = {} #initialize the packet dictionary
packetCounter = 0 #global counter for dictionary elements

#---------------------------------------------------HELPER-FUNCTIONS-END----------------------------------------------------#

#---------------------------------------------------PacketCaptureThread-----------------------------------------------------#
#thread class for capturing packets in real time
class PacketCaptureThread(QThread):
    packetCaptured = pyqtSignal(int) #signal for the thread to update the main for changes
    setGUIState = pyqtSignal(bool) #signal for the thread to set the GUI elements from the main window
    permissionError = pyqtSignal() #signal for permission error to tell GUI to show messagebox for error
    interface = None #interface of network 
    packetQueue = None #packet queue pointer for the thread
    packetFilter = None #represents the packet type filter for sniffer
    PortandIp = None #string that represents port and ip for sniffer to filter with
    packetList = None #packet list for loading scan with pcap file
    stopCapture = False #flag for capture status

    def __init__(self, packetQueue, packetFilter, PortandIp, interface='', packetList=None):
        super(PacketCaptureThread, self).__init__()
        self.interface = interface #initialize the network interface if given
        self.packetQueue = packetQueue #setting the packetQueue from the packet sniffer class
        self.packetFilter = packetFilter #set the packet filter for scapy sniff method
        self.PortandIp = PortandIp #set the port and ip string for filthering with desired pord and ip
        self.packetList = packetList #set the packet list if given
        packetBuffer = 1000 if self.packetList else 500 #buffer for number of packets added to GUI
        self.updateTimer = QTimer(self) #initialzie the QTimer
        self.updateTimer.timeout.connect(lambda: self.packetCaptured.emit(packetBuffer)) #connect the signal to gui to update the packet list when timer elapses
        self.updateTimer.start(2000) #setting the timer to elapse every 2 seconds (can adjust according to the load)


    #methdo that handles stopping the scan
    def stop(self):
        self.stopCapture = True #setting the stop flag to true will stop the loop in sniff


    #method for sniff method of scapy to know status of flag 
    def checkStopFlag(self, packet):
        return self.stopCapture #return the stopCapture flag


    #method that handles the packet capturing
    def PacketCapture(self, packet): 
        #for each packet we receive we send it to the dict to determine its identity and call the necessary handle method
        for packetType, handler in self.packetFilter.items():
            if packet.haslayer(packetType): #if we found matching packet we call its handle method
                handledPacket = handler(packet) #call handler method of each packet
                if handledPacket != None: #check if its not none
                    self.packetQueue.put(handledPacket.info()) #we put the packet's info in the queue for later use 
                break #break from the loop when handled the packet


    #run method for the thread, initialzie the scan, call scapy sniff method with necessary parameters
    def run(self):
        self.setGUIState.emit(False) #set GUI elements to be unclickable for scan
        if self.packetList is not None: #if true we received a packet list meaning we need to load scan from pcap file
            for packet in self.packetList: #iterate through the packet list 
                self.PacketCapture(packet) #call packetCapture method for each packet in list
            while not self.packetQueue.empty(): #now we keep thread alive until all packets were loaded
                if self.packetQueue.empty(): #if true the queue is empty so we can finish
                    break #break the loop to end loading
                QThread.sleep(2) #we give the thread to sleep for 2 seconds for gui responsiveness
        else: #else we need to start a regular scan
            try: #we call sniff with desired interface and filters for port and ip
                sniff(iface=self.interface, prn=self.PacketCapture, filter=self.PortandIp, stop_filter=self.checkStopFlag, store=0)
            except PermissionError: #if user didn't run in administrative privileges we emit signal to show messagebox with error
                self.permissionError.emit() #emit a signal to GUI to show permission error message box
                print('Permission denied. Please run again with administrative privileges.') #print permission error message in terminal
            except Exception as e: #we catch an exception if something happend while sniffing
                print(f'An error occurred while sniffing: {e}') #print error message in terminal
        self.setGUIState.emit(True) #after thread finishes we set the GUI elements to be clickable again

#--------------------------------------------------PacketCaptureThread-END--------------------------------------------------#

#-------------------------------------------------------Application---------------------------------------------------------#
#main class for the application that handles the GUI and the packet sniffing
class PacketSniffer(QMainWindow):
    packetCaptureThread = None #current thread that capturing packets 
    packetModel = None #packet list model for QListView 
    packetQueue = None #queue for packets before adding them to list (thread safe)
    validIp = True #set validIp flag to true
    isClosing = False #set isClosing flag to false

    def __init__(self):
        super(PacketSniffer, self).__init__()
        loadUi('SniffSerpent.ui', self) #load the ui file of the sniffer
        self.initUI() #call init method
        self.packetModel = QStandardItemModel() #set the QListView model for adding items to it
        self.PacketList.setModel(self.packetModel) #set the model for the packetlist in gui
        self.packetQueue = Queue() #initialize the packet queue
        
    
    #method to initialize GUI methods and events
    def initUI(self):
        self.setWindowTitle('SniffSerpent') #set title of window
        self.setWindowIcon(QIcon('images/serpent.ico')) #set icon of window
        infoImageLabel = ImageLabel(1548, 10, 40, 40, 'images/infoTitle.png', True, self) #create a image label for info icon
        infoImageLabel.setToolTip('<html><head/><body><p><span style="font-size:10pt;">General information about SniffSerpent.</span></p></body></html>') #set toolTip for info icon
        self.StartScanButton.clicked.connect(self.StartScanClicked) #add method to handle start scan button
        self.StopScanButton.clicked.connect(self.StopScanClicked) #add method to handle stop scan button 
        self.LoadScanButton.clicked.connect(self.LoadScanClicked) #add method to handle load scan button
        self.ClearButton.clicked.connect(self.ClearClicked) #add method to handle clear button 
        self.SaveScanButton.clicked.connect(self.SaveScanClicked) #add method to handle save scan button
        infoImageLabel.clicked.connect(self.infoImageLabelClicked) #add method to handle clicks on infoImageLabel
        self.PacketList.doubleClicked.connect(self.handleItemDoubleClicked) #add method to handle clicks on the items in packet list
        self.setLineEditValidate() #call the method to set the validators for the QLineEdit for port and ip
        self.IPLineEdit.textChanged.connect(self.checkIPValidity) #connect signal for textChanged for IP to determine its validity
        self.initComboBox() #set the combobox interface names 
        self.center() #make the app open in center of screen
        self.show() #show the application
		

    #method for closing the program and managing the packetCapture thread
    def closeEvent(self, event):
        if self.packetCaptureThread is not None and self.packetCaptureThread.isRunning(): #if true we have a scan running
            self.isClosing = True #set the isClosing flag to true to indicate that user wants to close program
            self.StopScanClicked() #call StopScanClicked method to stop the scan
        event.accept() #accept the close event


    #method for making the app open in the center of screen
    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
    

    #method to check the IP Line edit validity in gui (using signals)
    def checkIPValidity(self):
        ip = self.IPLineEdit.text().strip() #get the ip user entered in gui
        if ip: #if ip is set, we check
            octets = ip.split('.') #splite the ip into 4 octets
            self.validIp = (len(octets) == 4 and all(o.isdigit() and 0 <= int(o) <= 255 for o in octets))  #check if ip is valid and not missing numbers (e.g 192.168.1.1)
        else: #else ip is empty so its not specified by user (optional)
            self.validIp = True #set the validIp flag to true
        if self.validIp: #if ip is valid we set the default style of the edit line lable
            style = 'QLineEdit { background-color: rgba(32,33,35,255); border-radius: 15px; border-style: outset; border-width: 2px; border-radius: 15px; border-color: black; padding: 4px; }'
            self.IPLineEdit.setStyleSheet(style)
        else: #else the user input is invalid, we show a red border on the edit line lable for error indication
            style = 'QLineEdit { background-color: rgba(32,33,35,255); border-radius: 15px; border-style: outset; border-width: 2px; border-radius: 15px; border-color: rgb(139,0,0); padding: 4px; }'
            self.IPLineEdit.setStyleSheet(style)
    

    #method for setting the settings for ip and port line edit lables
    def setLineEditValidate(self):
        IPRegex = QRegExp(r"^((25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)$") #regex for IP template (192.168.1.1)
        IPValidator = QRegExpValidator(IPRegex) #create the validator for ip using the regex
        portValidator = QIntValidator(0, 65535) #create a validator for port (number between 0 to 65535)
        self.IPLineEdit.setValidator(IPValidator) #set validator for IP
        self.PortLineEdit.setValidator(portValidator) #set validaotr for port
    
    
    #method for setting the parameters for the interfaces combobox 
    def initComboBox(self):
        self.InterfaceComboBox.view().window().setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.InterfaceComboBox.view().window().setAttribute(Qt.WA_TranslucentBackground)
        interfaces = getNetworkInterfaces() #call our method to receive the network interfaces
        interfaces = ['Loopback' if interface == '\\Device\\NPF_Loopback' else interface for interface in interfaces] #replace the loopback interface name
        if interfaces: #if not empty we add them to the combobox
            self.InterfaceComboBox.addItems(interfaces) #add items to combobox
        if len(interfaces) >= 2: #if we have more then one available interface 
            self.InterfaceComboBox.addItem('All') #we add "All" option to scan all available interfaces
    
    
    #method that return desktop directory if available, else the home directory
    def getDirectory(self):
        defaultDirectory = os.path.join(os.path.expanduser('~'), 'Desktop') #set default directory to be desktop 
        if not os.path.exists(defaultDirectory): #if desktop directory isn't available we try specific os paths
            if sys.platform.startswith('darwin'):  #if os is macOS
                defaultDirectory = os.path.join(os.path.join('/Users/', os.getlogin()), 'Desktop') #set macOS specific desktop path
            elif sys.platform.startswith('linux'):  #if os is Linux
                defaultDirectory = os.path.join(os.path.join('/home/', os.getlogin()), 'Desktop') #set Linux specific desktop path
            else: #else we set the default directory to home directory
                defaultDirectory = os.path.expanduser('~') #setting the default directory to be home directory
        return defaultDirectory

    
    #method for sniff method for permission error exceptions
    def sniffErrorMessageBox(self):
        CustomMessageBox('Permission Denied', 'Sniffing unavailable, please run again with administrative privileges.', 'Critical', True) #show permission error message box
        sys.exit(1) #exit the program due to insufficient privileges


    #method for initialize the packet thread
    def initPacketThread(self, packetFilter, PortAndIP, interface='', packetList=None):
        self.packetCaptureThread = PacketCaptureThread(self.packetQueue, packetFilter, PortAndIP, interface, packetList) #initialzie the packet thread with the queue we initialized and interface
        self.packetCaptureThread.packetCaptured.connect(self.updatePacketList) #connect the packet thread to updatePacketList method
        self.packetCaptureThread.setGUIState.connect(self.handleGUIState) #connect the packet thread to handleGUIState method
        self.packetCaptureThread.permissionError.connect(self.sniffErrorMessageBox) #connnect the packet thread to sniffErrorMessageBox method
        self.packetCaptureThread.start() #calling the run method of the thread to start the scan    


    #method to handle the start scan button, initializing the packet sniffing
    def StartScanClicked(self):
        if self.packetCaptureThread is None or not self.packetCaptureThread.isRunning(): #checks if no thread is set for sniffer  
            try:
                packetFilter = self.packetFilter() #call packet filter for filtered dictionary based on check boxes state
                PortAndIP = self.getPortIP() #call the getPortId method to recevie the input for port and ip from user
            except (Exception, ValueError) as e: #if an exception is raised we show a messagebox for user with the error
                title = 'Format Error' if not self.validIp else 'Type Error'
                icon = 'Warning' if title == 'Format Error' else 'Critical'
                CustomMessageBox(title, str(e), icon) #show error message box
                return #stop the initialization of scan
            self.ClearClicked() #call clear method for clearing the memory and screen for new scan
            interface = self.InterfaceComboBox.currentText() #get the chosen network interface from combobox
            if interface == '': #if the input is empty it means no availabe interface found
                CustomMessageBox('No Available Interface', 'Cannot find available network interface.', 'Critical', False) #show error message box
                return #stop the initialization of scan
            elif interface == 'All': #if user chose "All" option so we scan all available network interfaces
                self.initPacketThread(packetFilter, PortAndIP) #initialzie the packet thread without specifing a interface, we scan all interfaces
            elif interface == 'Loopback': #if true we need to scan on loopback interface on windows
                interface = '\\Device\\NPF_Loopback' #set interface to be loopback interface name
                self.initPacketThread(packetFilter, PortAndIP, interface) #initialzie the packet thread
            else: #if true it means we need to scan on a specific interface
                self.initPacketThread(packetFilter, PortAndIP, interface) #initialzie the packet thread
            self.StartScanButton.setEnabled(False) #set the scan button to be unclickable while scan in progress
        else: #else we show error message
            CustomMessageBox('Scan Running', 'Scan in progress!', 'Warning', False) #show error message box


    #method to handle the stop scan button, stops the packet sniffing
    def StopScanClicked(self):
        if self.packetCaptureThread is not None and self.packetCaptureThread.isRunning(): #checks if there is a running thread
            self.packetCaptureThread.stop() #calls stop method of the thread 
            self.packetCaptureThread.exit() #calls exit method of the thread 
            self.packetCaptureThread = None #setting the packetCaptureThread to None for next scan 
            self.handleGUIState(True) #we set the GUI elements to be clickable again
            self.StartScanButton.setEnabled(True) #set scan button back to being clickable
            if not self.isClosing: #if false we show messagebox
                CustomMessageBox('Scan Stopped', 'Packet capturing stopped.', 'Information', False) #show messagebox
            else: #else user wants to close program
                self.isClosing = False #set isClosing flag to false
                self.close() #call close method to close program
    
    
    #method for saving scan data into a text file
    def SaveScanClicked(self):
        #if packet dictionary isn't empty and if there's no scan in progress we open the save window
        if any(packetDictionary.values()) and (self.packetCaptureThread is None or not self.packetCaptureThread.isRunning()):
            defaultFilePath = os.path.join(self.getDirectory(), 'Packet Scan') #we set the default file name, user can change that in dialog
            options = QFileDialog.Options() #this is for file options
            filePath, fileType = QFileDialog.getSaveFileName(self, 'Save Scan Data', defaultFilePath, 'Text File (*.txt);;PCAP File (*.pcap)', options=options) #save the file in a specific path
            if filePath: #if user chose valid path we continue
                filePath, _ = os.path.splitext(filePath) #remove extension if added during getSaveFileName method
                try: 
                    if fileType == 'PCAP File (*.pcap)': #means user chose pcap file
                        packetList = [packet.getPacket() for packet in packetDictionary.values()] #we convert the packet dictionary to list for scapy wrpcap method
                        wrpcap(filePath + '.pcap', packetList) #call wrpcap method to write the captured packets into pcap file
                        CustomMessageBox('Scan Saved', 'Saved scan detalis to PCAP file.', 'Information', False) #notify the user for success
                    else: #else user chose a txt file
                        with open(filePath + '.txt', 'w') as file: #we open the file for writing
                            for packet in packetDictionary.values(): #iterating over the packet dictionary to extract the info 
                                file.write('------------------------------------------------------------------------------------\n\n')
                                file.write(packet.moreInfo()) #write the packet info to the file (extended information)
                                file.write('------------------------------------------------------------------------------------\n\n')
                            CustomMessageBox('Scan Saved', 'Saved scan detalis to text file.', 'Information', False) #notify the user for success
                except Exception as e: #if error happend we print the error to terminal
                    print(f'Error occurred while saving: {e}')
            else: #else user didnt specify a file path
                CustomMessageBox('Save Error', 'You must choose a file type for saving!', 'Critical', False) #show error message box
        elif self.packetCaptureThread is not None and self.packetCaptureThread.isRunning(): #if scan in progress we notify the user
            CustomMessageBox('Scan In Progress', 'Cannot save scan while scan in progress!', 'Warning', False) #show error message box  
        else: #else we show a "saved denied" error if something happend
            CustomMessageBox('Save Denied', 'No scan data to save.', 'Information', False) #show error message box

    
    #method to handle loading pcap file scan data to interface
    def LoadScanClicked(self):
        if self.packetCaptureThread is None or not self.packetCaptureThread.isRunning(): #if there's no scan in progress we can load pcap file
            try:
                packetFilter = self.packetFilter() #call packet filter for filtered dictionary based on check boxes state
                PortAndIP = self.getPortIP() #call the getPortId method to recevie the input for port and ip from user
            except (Exception, ValueError) as e: #if an exception is raised we show a messagebox for user with the error
                title = 'Format Error' if not self.validIp else 'Type Error'
                icon = 'Warning' if title == 'Format Error' else 'Critical'
                CustomMessageBox(title, str(e), icon) #show error message box
                return #stop the loading of pcap file
            options = QFileDialog.Options() #this is for file options
            options |= QFileDialog.ReadOnly #making the files read only so user wont be able to edit files while choosing a file
            filePath, fileType = QFileDialog.getOpenFileName(self, 'Choose PCAP File', self.getDirectory(), 'PCAP File (*.pcap)', options=options) #load the pcap file from a specific path
            if filePath and fileType == 'PCAP File (*.pcap)': #if the file path is valid we proceed and the type is pcap
                self.ClearClicked() #call clear method 
                packetList = rdpcap(filePath) #read all the content of the pcap file and save in variable
                self.initPacketThread(packetFilter, PortAndIP, None, packetList) #initialize the packet thread with packetList
                CustomMessageBox('Load Successful', 'Loaded PCAP file successfully, loading data to interface...', 'Information', True) #notify the user for success
            else: #else user didn't specify a file path
                CustomMessageBox('Load Error', 'You must choose a PCAP file to load!', 'Critical', False) #show error message box 
        else: #else we show error message
            CustomMessageBox('Scan Running', 'Scan in progress, cannot load file.', 'Warning', False) #show error message box


    #method to handle clearing the screen
    def ClearClicked(self):
        global packetDictionary #declare global parameter for clearing packet dictionary
        global packetCounter #declare global parameter for resetting the packet counter
        if self.packetCaptureThread is None or (self.packetCaptureThread is not None and not self.packetCaptureThread.isRunning()):
            packetDictionary.clear() #clear the main packet dictionary
            packetCounter = 0 #reset the packet counter
            self.packetQueue = Queue() #clear the queue if there're packets in
            self.PacketList.model().clear() #clear the packet list in GUI
            self.MoreInfoTextEdit.setText('') #clear the extended information in GUI
        elif self.packetCaptureThread is not None and self.packetCaptureThread.isRunning():
            CustomMessageBox('Thread Running Error', 'Cannot clear while scan is in progress!', 'Warning', False) #show error message box
        
    
    #method that shows information about SniffSerpent 
    def infoImageLabelClicked(self):
        sniffSerpentInfo = (
        '<br/>SniffSerpent is an easy to use packet sniffer that allows users to capture packets<br/> on various network interfaces, save packet scans in various file types<br/> as well as load PCAP files for future analysis.<br/><br/>'
        'SniffSerpent supports the following packet types:<br/>'
        'TCP, UDP, HTTP, DNS, TLS, ICMP, DHCP, ARP, IGMP, STP.<br/><br/>'
        'SniffSerpent is licensed under the MIT license, all rights are reserved<br/> to Shay Hahiashvili (Shayhha).<br/><br/>'
        'For questions or feedback, <a href="https://github.com/Shayhha/SniffSerpent">visit SniffSerpent on GitHub</a>.'
        )
        CustomMessageBox('SniffSerpent General Information', sniffSerpentInfo, 'NoIcon', False, 700, 360) #shows messagebox with info about the application


    #method that checks all the check boxs state, return a string with filtered packets
    def packetFilter(self):
        #check each check box to filter the packet kinds
        packetFilter = ''
        if not self.HTTPCheckBox.isChecked():
            packetFilter += 'HTTP,'
        if not self.TLSCheckBox.isChecked():
            packetFilter += 'TLS,'
        if not self.DHCPCheckBox.isChecked():
            packetFilter += 'DHCP,'
        if not self.DNSCheckBox.isChecked():
            packetFilter += 'DNS,'
        if not self.TCPCheckBox.isChecked():
            packetFilter += 'TCP,'
        if not self.UDPCheckBox.isChecked():
            packetFilter += 'UDP,'
        if not self.ICMPCheckBox.isChecked():
            packetFilter += 'ICMP,'
        if not self.ARPCheckBox.isChecked():
            packetFilter += 'ARP,'
        if not self.IGMPCheckBox.isChecked():
            packetFilter += 'IGMP,'
        if not self.STPCheckBox.isChecked():
            packetFilter += 'STP,'
        #dicionary for packet kinds and their methods for handling:
        captureDictionary = {
        HTTP: handleHTTP,
        TLS: handleTLS,
        DHCP: handleDHCP,
        DNS: handleDNS,
        TCP: handleTCP,
        UDP: handleUDP,
        ICMP: handleICMP,
        ARP: handleARP,
        IGMP: handleIGMP,
        STP: handleSTP,
        }
        if packetFilter != '': #if packetFilter isn't empty it means we need to filter the dictionary 
            packetFilter.rstrip(',').split(',') #splite the original string to get a list of the packet types
            temp = captureDictionary.copy() #save the original dictionary in temp var
            for packetType, handler in temp.items(): #iterating on the dictionary to remove the filtered packets
                if packetType == TLS: #if true we need to strip a TLS packet string
                    p = str(packetType).split('.')[4].rstrip("'>") #strip the str representation of the TLS packet for extracting its name
                else: #else its a regular packet so we strip it 
                    p = str(packetType).split('.')[3].rstrip("'>") #strip the str representation of the packet for extracting its name
                if p in packetFilter: #if true we need to delete the packet type from the dictionary
                    del captureDictionary[packetType] #delete packet from dictionary
        if not captureDictionary: #if dictionary is empty we raise a new exception to indicate of an error 
            raise Exception('Error, you must choose at least one type for scan.')
        return captureDictionary
     

    #method that checks the ip and port line edit lables, if valid it returns the string representing the option, else raises a ValueError exception
    def getPortIP(self):
        output = ''
        if self.IPLineEdit.text() != '': #if true user typed a ip for us to search for 
            if not self.validIp: #if ip isnt valid we raise a ValueError exeption
                raise ValueError('Error, please enter a valid IP address in the format {xxx.xxx.xxx.xxx}.')
            else: #else the ip is valid we add it to output string
                output += f'(src {self.IPLineEdit.text()} or {self.IPLineEdit.text()})'
        if self.PortLineEdit.text() != '': #if user typed a port to seach for
            if output != '': #if true we need to divide the ip and port with 'add' word 
                output += ' and ' #add the word that divides the ip and port
            output += f'port {self.PortLineEdit.text()}' #add the port to the output
        return output


    #method for updating the packet list
    def updatePacketList(self, maxSize=100):
        buffer = min(self.packetQueue.qsize(), maxSize) #buffer for the amount of packets to add at a time, min between queue size and maxSize value
        if self.packetCaptureThread != None and not self.packetQueue.empty(): #we add packets when queue if not empty 
            while buffer > 0: #add the packets to packet list while buffer isn't empty 
                packetInfo = self.packetQueue.get() #taking a packet from the queue
                self.packetModel.appendRow(QStandardItem(packetInfo)) #adding to packet list in GUI
                buffer -= 1 #subtracting from buffer


    #method the double clicks in packet list, extended information section
    def handleItemDoubleClicked(self, index):
        packetIndex = index.row() #get the index of the row of the specific packet we want
        item = self.PacketList.model().itemFromIndex(index) #taking the packet from the list in GUI
        if item is not None and packetIndex in packetDictionary: #checking if the packet in GUI list isn't None 
            p = packetDictionary[packetIndex] #taking the matching packet from the packetDictionary
            self.MoreInfoTextEdit.setText(p.moreInfo()) #add the information to the extended information section in GUI
    
    
    #method to handle state of checkboxes, if state false we disable them, otherwise we enable them
    def handleGUIState(self, state):
        if state: #if true we set the checkboxes and ip/port line edit to be enabled
            self.HTTPCheckBox.setEnabled(True)
            self.TLSCheckBox.setEnabled(True)
            self.TCPCheckBox.setEnabled(True)
            self.DNSCheckBox.setEnabled(True)
            self.UDPCheckBox.setEnabled(True)
            self.ICMPCheckBox.setEnabled(True)
            self.DHCPCheckBox.setEnabled(True)
            self.ARPCheckBox.setEnabled(True)
            self.IGMPCheckBox.setEnabled(True)
            self.STPCheckBox.setEnabled(True)
            self.IPLineEdit.setEnabled(True)
            self.PortLineEdit.setEnabled(True)
            self.InterfaceComboBox.setEnabled(True)
        else: #else we disable the checkboxes and ip/port line edit
            self.HTTPCheckBox.setEnabled(False)
            self.TLSCheckBox.setEnabled(False)
            self.TCPCheckBox.setEnabled(False)
            self.DNSCheckBox.setEnabled(False)
            self.UDPCheckBox.setEnabled(False)
            self.ICMPCheckBox.setEnabled(False)
            self.DHCPCheckBox.setEnabled(False)
            self.ARPCheckBox.setEnabled(False)
            self.IGMPCheckBox.setEnabled(False)
            self.STPCheckBox.setEnabled(False)
            self.IPLineEdit.setEnabled(False)
            self.PortLineEdit.setEnabled(False)
            self.InterfaceComboBox.setEnabled(False)
            
#------------------------------------------------------Application-END------------------------------------------------------#

#--------------------------------------------------------ImageLabel---------------------------------------------------------#
class ImageLabel(QLabel):
    clicked = pyqtSignal() #clicked signal 
    isClickable = None #flag for indicating if label is clickable
    
    def __init__(self, x, y, width, height, pixmapPath, isClickable, parent=None):
        super().__init__(parent) #call default QLabel ctor
        self.isClickable = isClickable #set the isClickable flag
        self.setPixmap(QPixmap(pixmapPath)) #set the path for image 
        self.setStyleSheet('QLabel { background: none; }') #set the backgorund to be transparent
        self.setGeometry(x, y, width, height) #set the position for label in GUI
        self.setMouseTracking(True) #set mouse tracking to be enabled

    #method for mouse press event
    def mousePressEvent(self, event):
        if self.isClickable:
            self.clicked.emit() #emit the clicked signal 

    #method for mouse enter event
    def enterEvent(self, event):
        if self.isClickable:
            self.setCursor(Qt.PointingHandCursor) #set the cursor to be pointing hand

    #method for mouse leave event
    def leaveEvent(self, event):
        if self.isClickable:
            self.unsetCursor() #set back cursor to be regular

#------------------------------------------------------ImageLabel-END-------------------------------------------------------#

#-----------------------------------------------------CustomMessageBox------------------------------------------------------#
class CustomMessageBox(QDialog):
    def __init__(self, title, text, icon='NoIcon', wordWrap=True, width=400, height=150, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title) #set the title for message box
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint) #set the window flags
        self.wordWrap = wordWrap #set the wordWrap for text
        self.setFixedSize(QSize(width, height)) #set the width and height for window
        self.setStyleSheet('background-color: rgb(245,245,245);') #set backgorund color
        self.initMessageBox(text, icon) #call initMessageBox for initializing the message box
        self.exec_() #execute the message box (show)

    def initMessageBox(self, text, icon):
        layout = QVBoxLayout() #create new layout
        horizontalLayout = QHBoxLayout() #create new horizontal layout
        textLabel = QLabel(text) #creat a text lable 
        textLabel.setAlignment(Qt.AlignCenter)  #set text alignment to center
        textLabel.setStyleSheet('font-size: 18px;') #set font size of text
        textLabel.setWordWrap(self.wordWrap) #set a wordWrap for better text representation
        textLabel.setOpenExternalLinks(True)  #open links in an external web browser
            
        if icon != 'NoIcon': #if true it means we need to set an icon for message box
            iconLabel = QLabel()
            if icon == 'Information':
                iconLabel.setPixmap(QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation).pixmap(QSize(64, 64)))
                self.setWindowIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
            elif icon == 'Warning':
                iconLabel.setPixmap(QApplication.style().standardIcon(QStyle.SP_MessageBoxWarning).pixmap(QSize(64, 64)))
                self.setWindowIcon(self.style().standardIcon(QStyle.SP_MessageBoxWarning))
            elif icon == 'Critical':
                iconLabel.setPixmap(QApplication.style().standardIcon(QStyle.SP_MessageBoxCritical).pixmap(QSize(64, 64)))
                self.setWindowIcon(self.style().standardIcon(QStyle.SP_MessageBoxCritical))
            elif icon == 'Question':
                iconLabel.setPixmap(QApplication.style().standardIcon(QStyle.SP_MessageBoxQuestion).pixmap(QSize(64, 64)))
                self.setWindowIcon(self.style().standardIcon(QStyle.SP_MessageBoxQuestion))
            iconLabel.setAlignment(Qt.AlignLeft) #set the icon to the left
            spacer = QSpacerItem(10, 10, QSizePolicy.Fixed, QSizePolicy.Fixed) #create new spacer for the message box
            horizontalLayout.addWidget(iconLabel) #add the icon to layout
            horizontalLayout.addItem(spacer) #add the spacer to layout
            horizontalLayout.addWidget(textLabel) #add the text label to layout
        else: #else no need for an icon 
            self.setWindowIcon(QIcon('images/serpent.ico')) #add default window icon
            horizontalLayout.addWidget(textLabel) #add only the text label to layout

        horizontalLayout.setAlignment(Qt.AlignCenter) #set alignment of horizontal layout
        layout.addLayout(horizontalLayout) #add the horizontal layout to the vertical layout
        OKButton = QPushButton('OK') #create new OK button
        layout.addWidget(OKButton, alignment=Qt.AlignCenter) #add the button to the layout
        style = '''
            QPushButton {
                background-color: rgba(32,33,35,255);
                color: rgb(245,245,245);
                border: 2px solid black;
                border-radius: 15px;
                padding: 4px;
                font-size: 17px; 
                font-family: Arial; 
                min-width: 60px;  
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: rgb(87, 89, 101);
            }
            QPushButton:pressed {
                background-color: rgb(177, 185, 187);
            }
        '''
        OKButton.setStyleSheet(style) #set stylesheet for the OK button
        OKButton.clicked.connect(self.accept) #set an accept operation to the clicks of OK button
        self.setLayout(layout) #finally set the layout of the messsage box

#---------------------------------------------------CustomMessageBox-END----------------------------------------------------#

#-----------------------------------------------------------MAIN------------------------------------------------------------#

if __name__ == '__main__':
    #----------------APP----------------#
    app = QApplication(sys.argv)
    sniffer = PacketSniffer()
    try:
        sys.exit(app.exec_())
    except:
        print('Exiting')
    #----------------APP----------------#
    #getAvailableInterfaces()

#-----------------------------------------------------------MAIN-END---------------------------------------------------------#