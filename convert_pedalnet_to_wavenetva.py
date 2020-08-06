import argparse
import numpy as np
import json

from model import PedalNet

def convert(args):
    ''' 
    TODO: converted model plays in WaveNetVA plugin, but doesn't sound right. Sound doesn't match PedalNet converted wav files.
    
    Converts a *.ckpt model from PedalNet into a .json format used in WaveNetVA. 

              Current changes to the original PedalNet model to match WaveNetVA include:
                1. Added CausalConv1d() to use causal padding
                2. Added an input layer, which is a Conv1d(in_channls=1, out_channels=num_channels, kernel_size=1)

                Note: The original PedalNet model was intended for use on PCM Int16 format wave files. The WaveNetVA is
                    intended as a plugin, which processes float32 audio data. The PedalNet model must be trained on wave files
                    saved as Float32 data, which has sample data in the range -1 to 1. 
              
              The model parameters used for conversion testing match the Wavenetva1 model (untested with other parameters):
              --num_channels=16, --dilation_depth=10, --num_repeat=1, --kernel_size=3
    '''

    # Permute tensors to match Tensorflow format with .permute(a,b,c):
    #a, b, c = 0, 1, 2  # Original shape  (creates heavily distorted signal for ts9, but not right)
    a, b, c = 2, 1, 0  # Pytorch uses (out_channels, in_channels, kernel_size), TensorFlow uses (kernel_size, in_channels, out_channels)
    model = PedalNet.load_from_checkpoint(checkpoint_path=args.model)

    sd = model.state_dict()

    # Get hparams from model
    hparams = model.hparams
    residual_channels = hparams["num_channels"]
    filter_width = hparams["kernel_size"]
    dilations = [2 ** d for d in range(hparams["dilation_depth"])] * hparams["num_repeat"]

    data_out = {"activation": "gated", 
                "output_channels": 1, 
                "input_channels": 1, 
                "residual_channels": residual_channels, 
                "filter_width": filter_width, 
                "dilations": dilations, 
                "variables": []}

    # Use pytorch model data to populate the json data for each layer
    for i in range(-1, len(dilations) + 1):
        # Input Layer
        if i == -1: 
            data_out["variables"].append({"layer_idx":i,
                                        "data":[str(w) for w in (sd['wavenet.input_layer.weight']).permute(a,b,c).flatten().numpy().tolist()],
                                        "name":"W"})
            data_out["variables"].append({"layer_idx":i,
                                        "data":[str(b) for b in (sd['wavenet.input_layer.bias']).flatten().numpy().tolist()],
                                        "name":"b"})
        # Linear Mix Layer
        elif  i == len(dilations):  
            data_out["variables"].append({"layer_idx":i,
                                        "data":[str(w) for w in (sd['wavenet.linear_mix.weight']).permute(a,b,c).flatten().numpy().tolist()], 
                                        "name":"W"})

            data_out["variables"].append({"layer_idx":i,
                                        "data":[str(b) for b in (sd['wavenet.linear_mix.bias']).numpy().tolist()],
                                        "name":"b"})
        # Hidden Layers
        else:
            data_out["variables"].append({"layer_idx":i,
                                    "data":[str(w) for w in sd['wavenet.convs_tanh.' + str(i) + '.weight'].permute(a,b,c).flatten().numpy().tolist() +
                                    sd['wavenet.convs_sigm.' + str(i) + '.weight'].permute(a,b,c).flatten().numpy().tolist()], 
                                    "name":"W_conv"})
            data_out["variables"].append({"layer_idx":i,
                                        "data":[str(b) for b in sd['wavenet.convs_tanh.' + str(i) + '.bias'].flatten().numpy().tolist() + 
                                        sd['wavenet.convs_sigm.' + str(i) + '.bias'].flatten().numpy().tolist()],
                                        "name":"b_conv"})
            data_out["variables"].append({"layer_idx":i,
                                        "data":[str(w2) for w2 in sd['wavenet.residuals.' + str(i) + '.weight'].permute(a,b,c).flatten().numpy().tolist()],
                                        "name":"W_out"})
            data_out["variables"].append({"layer_idx":i,
                                        "data":[str(b2) for b2 in sd['wavenet.residuals.' + str(i) + '.bias'].flatten().numpy().tolist()],
                                        "name":"b_out"})

    #for debugging ###################
    #print("State Dict Data:")
    #for i in sd.keys():
    #    print(i, "  Shape: ", sd[i].shape)

    # output final dictionary to json file
    with open('converted_model.json', 'w') as outfile:
        json.dump(data_out, outfile)
    print("Need to remove the quotations around number values, can use  https://csvjson.com/json_beautifier")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/pedalnet.ckpt")
    args = parser.parse_args()
    convert(args)