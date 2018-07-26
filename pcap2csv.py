#!/usr/bin/env python3

"""pcap2csv
Script to extract specific pieces of information from a pcap file and
render into a csv file.

Usage: <program name> --pcap <input pcap file> --csv <output pcap file>

Each packet in the pcap is rendered into one row of the csv file.
The specific items to extract, and the order in which they are rendered
in the csv are hard-coded in the script, in the 'render_csv_row' function.
Also note that the separators in the csv are '|' characters, not commas.

This script uses *both* PyShark (https://kiminewt.github.io/pyshark/) and
Scapy to do its work. PyShark because we want to leverage tshark's powerful
protocol decoding ability to generate the "textual description" field of
the CSV, and Scapy because at the same time we want to access the "payload"
portion of the packet (PyShark seems to be unable to provide this).
"""

import argparse
import os.path
import sys

import pyshark
from scapy.utils import RawPcapReader
from scapy.layers.l2 import Ether
from scapy.layers.inet import IP, UDP, TCP

#--------------------------------------------------

def render_csv_row(pkt_sh, pkt_sc, fh_csv):
    """Write one packet entry into the CSV file.
    pkt_sh is the PyShark representation of the packet

    pkt_sc is a 'bytes' representation of the packet as returned from
    scapy's RawPcapReader

    fh_csv is the csv file handle
    """

    ip_pkt_sc = Ether(pkt_sc)[IP]       # <<<< Assuming Ethernet + IPv4 here
    proto = ip_pkt_sc.fields['proto']
    if proto == 17:
        udp_pkt_sc = ip_pkt_sc[UDP]
        l4_payload_bytes = bytes(udp_pkt_sc.payload)
        l4_proto_name = 'UDP'
        l4_sport = udp_pkt_sc.sport
        l4_dport = udp_pkt_sc.dport
    elif proto == 6:
        tcp_pkt_sc = ip_pkt_sc[TCP]
        l4_payload_bytes = bytes(tcp_pkt_sc.payload)
        l4_proto_name = 'TCP'
        l4_sport = tcp_pkt_sc.sport
        l4_dport = tcp_pkt_sc.dport
    else:
        # Currently not handling packets that are not UDP or TCP
        l4_payload_bytes = b'\x00'
        l4_proto_name = '???'

    # Each line of the CSV has this format
    fmt = '{0}|{1}|{2}({3})|{4}|{5}:{6}|{7}:{8}|{9}|{10}'
    #       |   |   |   |    |   |   |   |   |   |   |
    #       |   |   |   |    |   |   |   |   |   |   o-> {10} L4 payload hexdump
    #       |   |   |   |    |   |   |   |   |   o-----> {9}  total pkt length
    #       |   |   |   |    |   |   |   |   o---------> {8}  dst port
    #       |   |   |   |    |   |   |   o-------------> {7}  dst ip address
    #       |   |   |   |    |   |   o-----------------> {6}  src port
    #       |   |   |   |    |   o---------------------> {5}  src ip address
    #       |   |   |   |    o-------------------------> {4}  text description
    #       |   |   |   o------------------------------> {3}  L4 protocol
    #       |   |   o----------------------------------> {2}  highest protocol
    #       |   o--------------------------------------> {1}  time
    #       o------------------------------------------> {0}  frame number

    print(fmt.format(pkt_sh.no,               # {0}
                     pkt_sh.time,             # {1}
                     pkt_sh.protocol,         # {2}
                     l4_proto_name,           # {3}
                     pkt_sh.info,             # {4}
                     pkt_sh.source,           # {5}
                     l4_sport,                # {6}
                     pkt_sh.destination,      # {7}
                     l4_dport,                # {8}
                     pkt_sh.length,           # {9}
                     l4_payload_bytes.hex()), # {10}
          file=fh_csv)
#--------------------------------------------------

def pcap2csv(in_pcap, out_csv):
    """Main entry function called from main to process the pcap and
    generate the csv file.

    in_pcap = name of the input pcap file (guaranteed to exist)
    out_csv = name of the output csv file (will be created)

    This function walks over each packet in the pcap file, and for
    each packet invokes the render_csv_row() function to write one row
    of the csv.
    """

    # Open the pcap file with PyShark in "summary-only" mode, since this
    # is the mode where the brief textual description of the packet (e.g.
    # "Standard query 0xf3de A www.cisco.com", "Client Hello" etc.) are
    # made available.
    pcap_pyshark = pyshark.FileCapture(in_pcap, only_summaries=True)
    pcap_pyshark.load_packets()
    pcap_pyshark.reset()

    frame_num = 0
    with open(out_csv, 'w') as fh_csv:
        # Open the pcap file with scapy's RawPcapReader, and iterate over
        # each packet. In each iteration get the PyShark packet as well,
        # and then call render_csv_row() with both representations to generate
        # the CSV row.
        for pkt_scapy, _, (_, _, _) in RawPcapReader(in_pcap):
            try:
                pkt_pyshark = pcap_pyshark.next_packet()
                frame_num += 1
                render_csv_row(pkt_pyshark, pkt_scapy, fh_csv)
            except StopIteration:
                # Shouldn't happen because the RawPcapReader iterator should also
                # exit before this happens.
                break

    print('{} packets read'.format(frame_num))
#--------------------------------------------------

def command_line_args():
    """Helper called from main() to parse the command line arguments"""

    parser = argparse.ArgumentParser()
    parser.add_argument('--pcap', metavar='<input pcap file>',
                        help='pcap file to parse', required=True)
    parser.add_argument('--csv', metavar='<output csv file>',
                        help='csv file to create', required=True)
    args = parser.parse_args()
    return args
#--------------------------------------------------

def main():
    """Program main entry"""
    args = command_line_args()

    if not os.path.exists(args.pcap):
        print('Input pcap file "{}" does not exist'.format(args.pcap),
              file=sys.stderr)
        sys.exit(-1)

    if os.path.exists(args.csv):
        print('Output csv file "{}" already exists, '
              'won\'t overwrite'.format(args.csv),
              file=sys.stderr)
        sys.exit(-1)

    pcap2csv(args.pcap, args.csv)
#--------------------------------------------------

if __name__ == '__main__':
    main()
