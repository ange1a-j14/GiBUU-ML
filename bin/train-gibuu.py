#!/usr/bin/env python3

import yaml
import torch
import fire
import os
import time
import sys
import lightning.pytorch as pl

from gibuu_ml.utils import import_from
from gibuu_ml.cfg import prepare_cfg
from gibuu_ml.io import dataloader_factory

def train(
    cfg_file, 
    lr=None, load=None, resume=None, 
    max_epochs=10000, uid=False, log=None,
):

    # check input arguments
    assert (not load) or (not resume), \
        '--load and --resume cannot be used together'

    # prepare config dict
    with open(cfg_file, 'r') as f:
        cfg = yaml.safe_load(f)
    prepare_cfg(cfg)

    # TODO(2023-07-03 kvt) set learning rate
    if lr is not None:
        pass

    # dataloader
    dataloader = dataloader_factory(cfg)

    # uid
    pid = os.getpid()
    ts = int(time.time())

    # -------------------------------------------------------------------------
    # logger
    # -------------------------------------------------------------------------
    logger_cfg = cfg.setdefault('logger', {})

    if log is None:
        log_dir = logger_cfg.get('save_dir', 'logs')
        log_name = logger_cfg.get('name', None)
    else:
        log_dir, log_name = os.path.split(log)

    if log_name is None:
        log_name = 'gibuu'
        uid = True

    if uid:
        log_name = f'{log_name}_{ts:x}_{pid}'

    logger_cfg['save_dir'] = log_dir
    logger_cfg['name'] = log_name
    logger = pl.loggers.CSVLogger(**logger_cfg)
    
    # -------------------------------------------------------------------------
    # model
    # -------------------------------------------------------------------------
    Model = import_from(cfg['class']['model'])
    train_cfg = cfg.setdefault('training', {})
    train_cfg['runtime'] = {'max_epochs': max_epochs}
    runtime_cfg = train_cfg['runtime']

    if load is None:
        model = Model(cfg)
    else:
        print(f'[INFO] load {load}')
        model = Model.load_from_checkpoint(load, strict=False, cfg=cfg)
        runtime_cfg['load'] = load

    # -------------------------------------------------------------------------
    # Trainer + Checkpoint
    # -------------------------------------------------------------------------
    ckpt_callback = pl.callbacks.ModelCheckpoint(
        **train_cfg.get('checkpoint', {})
    )

    trainer_kwargs = train_cfg.get('trainer', {}).copy()
    trainer_kwargs.update(dict(
        max_epochs=max_epochs,
        logger=logger,
        callbacks=[ckpt_callback],
    ))

    trainer = pl.Trainer(**trainer_kwargs)
    if resume is not None:
        runtime_cfg['resume'] = resume

    # -------------------------------------------------------------------------
    # save cfg file
    # -------------------------------------------------------------------------
    cfg_dir = os.path.join(log_dir, log_name, 'cfg')
    if not os.path.isdir(cfg_dir):
        os.makedirs(cfg_dir)
    with open(f'{cfg_dir}/gibuu_{ts:x}_{pid}.yaml', 'w') as f:
        yaml.safe_dump(cfg, f)

    # -------------------------------------------------------------------------
    # start training
    # -------------------------------------------------------------------------
    if resume is None:
        trainer.fit(model, dataloader)
    else:
        print(f'[INFO] resume {resume}')
        trainer.fit(model, dataloader, ckpt_path=resume)

if __name__ == '__main__':
    fire.Fire(train)
