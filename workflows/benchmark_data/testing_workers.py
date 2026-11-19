"""Importable synthetic IPC workers for tests; never invoke chemistry or Slurm."""
import time


def geometry_container_worker(connection):
    connection.send({'event':'ready'})
    while True:
        task=connection.recv()
        if task is None:return
        time.sleep(.05)
        connection.send({'event':'result','mid':task['mid'],
            'result':{'state':'SYNTHETIC_CONTAINER_READY','value':task['model_smiles']}})


def pprime_container_worker(connection,root,snapshot,workers,deadline,stop_event):
    connection.send({'event':'ready'})
    while True:
        task=connection.recv()
        if task is None:return
        time.sleep(.01)
        connection.send({'event':'result','record_id':task['record_id'],
            'result':{'state':'SYNTHETIC_CLOSED','all_twelve_tasks_success':False}})