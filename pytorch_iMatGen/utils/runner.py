import os
import gc
import time
import torch
import numpy as np  # noqa
import pandas as pd
from tqdm import tqdm


class AutoEncoderRunner:
    def __init__(self, device='cpu'):
        self.device = device

    def train(self, model, criterion, optimizer, loaders, scheduler=None, logdir=None,
              num_epochs=20, score_func=None):
        # validation
        for dict_val in [loaders]:
            if 'train' in dict_val and 'valid' in dict_val:
                pass
            else:
                raise ValueError('You should set train and valid key.')

        # setup training
        model = model.to(self.device)
        train_loader = loaders['train']
        valid_loader = loaders['valid']
        best_score = -1.0
        best_avg_val_loss = 100
        log_df = pd.DataFrame(
            [], columns=['epoch', 'loss', 'valid_loss', 'score', 'time'],
            index=range(num_epochs)
        )
        for epoch in range(num_epochs):
            start_time = time.time()
            # release memory
            torch.cuda.empty_cache()
            gc.collect()
            # train for one epoch
            avg_loss = self._train_model(model, criterion, optimizer, train_loader, scheduler)
            # evaluate on validation set
            avg_val_loss, score = self._validate_model(model, criterion, valid_loader, score_func)

            # log
            elapsed_time = time.time() - start_time
            log_df[epoch, :] = [epoch + 1, avg_loss, avg_val_loss, score, elapsed_time]

            # save best params
            save_path = 'best_model.pth'
            if logdir is not None:
                save_path = os.path.join(logdir, save_path)

            if score_func is None:
                if best_avg_val_loss > avg_val_loss:
                    best_avg_val_loss = avg_val_loss
                    best_param_loss = model.state_dict()
                    torch.save(best_param_loss, save_path)
                    print('Save the best model on Epoch {}'.format(epoch + 1))
            else:
                if best_score < score:
                    best_score = score
                    best_param_score = model.state_dict()
                    torch.save(best_param_score, save_path)
                    print('Save the best model on Epoch {}'.format(epoch + 1))

            # save log
            log_df.to_csv(os.path.join(logdir, 'log.csv'))

        return True

    def _train_model(self, model, criterion, optimizer, train_loader, scheduler=None):
        # switch to train mode
        model.train()
        avg_loss = 0.0
        for idx, batch in tqdm(enumerate(train_loader), total=len(train_loader)):
            images = batch
            images = images.to(self.device)

            # training
            output = model(images)
            loss = criterion(output, images)

            # update params
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            # the position of this depends on the scheduler you use
            if scheduler is not None:
                scheduler.step()

            # calc loss
            avg_loss += loss.item() / len(train_loader)

        return avg_loss

    def _validate_model(self, model, criterion, valid_loader, score_func=None):
        # switch to eval mode
        model.eval()
        avg_val_loss = 0.
        score = None
        with torch.no_grad():
            for idx, batch in tqdm(enumerate(valid_loader), total=len(valid_loader)):
                images = batch
                images = images.to(self.device)

                # output
                output = model(images)
                loss = criterion(output, images)
                avg_val_loss += loss.item() / len(valid_loader)

        return avg_val_loss, score
