#!/usr/bin/env python

# Dovecot mdbox extractor
#
# Extract all mail from a Dovecot mdbox storage file.
#
# (c) 2019 Andreas Thienemann <andreas@bawue.net>

# Data taken from
# https://github.com/dovecot/core/blob/master/src/lib-storage/index/dbox-common/dbox-file.h
# https://github.com/dovecot/core/blob/master/src/doveadm/doveadm-dump-dbox.c might also be interesting

import sys
import re
import pprint
import email
import email.header
import base64

DBOX_VERSION = 2
DBOX_MAGIC_PRE = "\001\002"
DBOX_MAGIC_POST = "\n\001\003\n"
DBOX_HEADER_MSG_HEADER_SIZE= None
DBOX_HEADER_CREATE_STAMP = None

DBOX_META_HEADER = {'G': 'GUID',
                    'P': 'POP3_UIDL',
                    'O': 'POP3_ORDER',
                    'R': 'RECEIVED_TIME',
                    'Z': 'PHYSICAL_SIZE',
                    'V': 'VIRTUAL_SIZE',
                    'X': 'EXT_REF',
                    'B': 'ORIG_MAILBOX'}

attachment_store = '/var/spool/imap/attachments/'
file = sys.argv[1]

mdbox = ''

# Verify header
with open(file) as f:
  i = 0
  for line in f.readlines():
    if i == 0:
      res = re.match(r'^{} M(\w+) C(\w+)'.format(DBOX_VERSION), line)
      DBOX_HEADER_MSG_HEADER_SIZE = int(res.groups()[0], 16)
      DBOX_HEADER_CREATE_STAMP = int(res.groups()[1], 16)
    else:
      mdbox += line
    i += 1

# Split mails
for item in re.split(r'{}N\s+(\w+)\n'.format(DBOX_MAGIC_PRE), mdbox, 0, re.MULTILINE)[1:]:
  if len(item) < 30:
    msg_size = item
    continue
  else:
    msg_text = item

  text, _ = msg_text.split(DBOX_MAGIC_POST)

  # Headers
  res = re.search(r'{}(.*)$'.format(DBOX_MAGIC_POST), msg_text, re.MULTILINE | re.DOTALL)
  fields = res.group().split('\n')
  meta = {}
  for field in fields:
    field = field.strip()
    if field == DBOX_MAGIC_POST.strip() or len(field) == 0:
      continue
    header = field[0]
    value = field[1:]
    if header == 'X':
      ext_attachments = zip(*(iter(field[1:].split()),) * 4)
    else:
      ext_attachments = []
    if header in ['P', 'O', 'R', 'Z', 'V']:
      value = int(value, 16)
    meta.update({DBOX_META_HEADER[header]: value})
  meta.update({'msg_size': msg_size})
  meta.update({'ext_attachments': ext_attachments})

  # Assemble full text mail
  if len(ext_attachments) > 0:
    pos_in = 0
    pos_out = 0
    assembled_text = ''
    for i in range(0, len(ext_attachments)):
      start, length, options, file_ref = ext_attachments[i]
      start = int(start)
      length = int(length)

      assembled_text += text[pos_in:start - pos_out + pos_in]
      pos_in += start - pos_out
      pos_out = start + length

      with open('{}/{}'.format(attachment_store, file_ref)) as file:
        if options == 'B76':
          assembled_text += base64.encodestring(file.read()).strip()

    assembled_text += text[pos_in:]
    text = assembled_text


  # Write out mail
  filename = '/tmp/extract/' + meta['ORIG_MAILBOX'].replace('/', '.')
  with open('{}.{}'.format(filename, meta['GUID']), 'w') as f:
    f.write(text)
  print 'Mail {} written to {}.{}'.format(int(meta['msg_uid'], 16), filename, meta['GUID'])
