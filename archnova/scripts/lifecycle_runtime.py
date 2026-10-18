# -*- coding: utf-8 -*-
"""Shared lifecycle receipts for network state and execution phases."""
from orchestrator import digest
PHASES={'preprocess','forward','training','benchmark','lowering','replay'}
def make_receipt(phase,reads,writes,state_refs=None,status='completed',contract_hash=None):
 if phase not in PHASES: raise ValueError('Unknown lifecycle phase')
 return {'phase':phase,'reads':sorted(set(reads)),'writes':sorted(set(writes)),'state_refs':sorted(set(state_refs or [])),'status':status,'contract_hash':contract_hash,'receipt_hash':digest({'phase':phase,'reads':sorted(set(reads)),'writes':sorted(set(writes)),'state_refs':sorted(set(state_refs or [])),'status':status,'contract_hash':contract_hash})}
def validate_receipt(receipt,expected_phase=None):
 required={'phase','reads','writes','state_refs','status','contract_hash','receipt_hash'}
 if set(receipt)!=required or receipt['phase'] not in PHASES or (expected_phase and receipt['phase']!=expected_phase):raise ValueError('Invalid lifecycle receipt')
 expected=make_receipt(receipt['phase'],receipt['reads'],receipt['writes'],receipt['state_refs'],receipt['status'],receipt['contract_hash'])['receipt_hash']
 if expected!=receipt['receipt_hash']:raise ValueError('Lifecycle receipt hash changed')
 return receipt
