"""
Copyright (C) 2019 NVIDIA Corporation.  All rights reserved.
Licensed under the CC BY-NC-SA 4.0 license (https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode).
"""

import sys
import traceback

import torch

from options.train_options import TrainOptions
import util.validation as validation
import data
from util.iter_counter import IterationCounter
from util.visualizer import Visualizer, visualize_sidebyside
from trainers.pix2pix_trainer import Pix2PixTrainer

# os.environ['CUDA_LAUNCH_BLOCKING'] = "1"
# parse options
opt = TrainOptions().parse()

# print options to help debugging
print(' '.join(sys.argv))

# load the dataset
dataloader = data.create_dataloader(opt)

# Validation
dataloader_val = data.create_inference_dataloader(opt)

# create trainer for our model
trainer = Pix2PixTrainer(opt)

# create tool for counting iterations
iter_counter = IterationCounter(opt, len(dataloader))

# create tool for visualization
visualizer = Visualizer(opt)

# opt.display_freq = 5
# opt.print_freq = 5
# opt.validation_limit = 5

try:
    for epoch in iter_counter.training_epochs():
        if iter_counter.current_epoch != epoch:
            # They are only equal at the very beginning and after loading a model
            iter_counter.record_epoch_start(epoch)

        for i, data_i in enumerate(dataloader, start=iter_counter.epoch_iter):
            iter_counter.record_one_iteration()

            # Training
            # train generator
            if i % opt.D_steps_per_G == 0:
                trainer.run_generator_one_step(data_i)

            # train discriminator
            trainer.run_discriminator_one_step(data_i)

            # Visualizations
            if iter_counter.needs_printing():
                losses = trainer.get_latest_losses(include_log_losses=True)
                visualizer.print_current_errors(epoch, iter_counter.total_steps_so_far,
                                                losses, iter_counter.time_per_iter)
                visualizer.plot_current_errors(losses, iter_counter.total_steps_so_far)

            if iter_counter.needs_displaying():
                data_visuals = {**data_i, 'fake': trainer.get_latest_generated()}
                # data_visuals = {'content': data_i['label'],
                #                 'style': data_i['style_image'],
                #
                #                        'target': data_i['target'], 'user': data_i['user'], 'filename': data_i['filename']}
                visualize_sidebyside(data_visuals, visualizer, epoch, iter_counter.total_steps_so_far, limit=8, log_key='train')

                with torch.no_grad():
                    # Log some stuff for training
                    validation.run_validation(dataloader, trainer.pix2pix_model, visualizer, epoch, iter_counter,
                                              limit=opt.validation_limit, log_key='train')
                    # Output VALIDATION images
                    validation.run_validation(dataloader_val, trainer.pix2pix_model, visualizer, epoch, iter_counter, limit=opt.validation_limit, log_key='val')

            if iter_counter.needs_saving():
                print('saving the latest model (epoch %d, total_steps %d)' %
                      (epoch, iter_counter.total_steps_so_far))
                trainer.save('latest')
                iter_counter.record_current_iter()

        trainer.update_learning_rate(epoch)
        iter_counter.record_epoch_end()

        if epoch % opt.save_epoch_freq == 0 or \
           epoch == iter_counter.total_epochs:
            print('saving the model at the end of epoch %d, iters %d' %
                  (epoch, iter_counter.total_steps_so_far))
            trainer.save('latest')
            trainer.save(epoch)
    print('Training was successfully finished.')

except (KeyboardInterrupt, SystemExit):
        print("KeyboardInterrupt. Shutting down.")
        print(traceback.format_exc())
except Exception as e:
    print(traceback.format_exc())
finally:
    print('saving the model before quitting')
    trainer.save('latest')
    iter_counter.record_current_iter()
    del dataloader_val
    del dataloader


