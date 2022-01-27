try:
    import biorbd
    import bioviz
except ModuleNotFoundError:
    pass
try:
    import pyosim
    import opensim
except ModuleNotFoundError:
    pass
from models.scaling import C3DtoTRC
import csv
from biosiglive.client import Client
from biosiglive.server import Server
from biosiglive.data_processing import read_data
import numpy as np
from time import sleep

def read_sto_mot_file(filename):
    """
        Read sto or mot file from Opensim
        ----------
        filename: path
            Path of the file witch have to be read
        Returns
        -------
        Data Dictionary with file informations
    """
    data = {}
    data_row = []
    first_line = ()
    end_header = False
    with open(f"{filename}", "rt") as f:
        reader = csv.reader(f)
        for idx, row in enumerate(reader):
            if len(row) == 0:
                pass
            elif row[0][:9] == "endheader":
                end_header = True
                first_line = idx + 1
            elif end_header is True and row[0][:9] != "endheader":
                row_list = row[0].split("\t")
                if idx == first_line:
                    names = row_list
                else:
                    data_row.append(row_list)

    for r in range(len(data_row)):
        for col in range(len(names)):
            if r == 0:
                data[f"{names[col]}"] = [float(data_row[r][col])]
            else:
                data[f"{names[col]}"].append(float(data_row[r][col]))
    return data


def EKF(model_path, scaling=False, off_line=True):
    if not off_line:
        server_ip = "192.168.1.211"
        server_port = 50000
        n_marks = 16
        for i in range(5):
            client = Client(server_ip, server_port, "TCP")
            markers_tmp = client.get_data(
                ["markers"], nb_frame_of_interest=100, read_frequency=100, nb_of_data_to_export=10, get_names=True
            )  # , get_kalman=False)
            sleep((1 / 100) * 10)
            if i == 0:
                mark_0 = markers_tmp["markers"]
                marker_names = markers_tmp["marker_names"]
                markers = np.array(mark_0).reshape((3, n_marks, 10))
            #
            else:
                mark_tmp = markers_tmp["markers"]
                mark_tmp = np.array(mark_tmp).reshape((3, n_marks, 10))
                markers = np.append(markers, mark_tmp, axis=2)
    else:
        mat = read_data(f"/home/amedeo/Documents/programmation/data_article/{subject}/{trial}")
        try:
            markers = mat["kin_target"][:3, :, :20]
        except:
            markers = mat["markers"][:3, :, :20]

    data_dir = f"/home/amedeo/Documents/programmation/data_article/{subject}"

    marker_names = ['STER', 'XIPH', 'C7', 'T10', 'CLAV_SC', 'CLAV_AC',
                    'SCAP_IA', 'Acrom', 'SCAP_AA', 'EPICl', 'EPICm', 'DELT', 'ARMl', 'STYLu', 'LARM_elb',
                    'STYLr']

    if scaling:
        # ---------- model scaling ------------ #
        from pathlib import Path
        osim_model_path = f"{data_dir}/Wu_Shoulder_Model_mod_wt_wrapp_{subject}.osim"
        model_output = f"{data_dir}/" + Path(osim_model_path).stem + f'_scaled.osim'
        # scaling_tool = f"{data_dir}/scaling_tool.xml"
        scaling_tool = "/home/amedeo/Documents/programmation/data_article/scaling_tool.xml"
        # opensim.ScaleTool().printToXML(scaling_tool)
        trc_file = f'{data_dir}/anato.trc'
        C3DtoTRC.WriteTrcFromMarkersData(trc_file,
                                         markers=markers[:3, :, :],
                                         marker_names=marker_names,
                                         data_rate=100,
                                         cam_rate=100,
                                         n_frames=markers.shape[2],
                                         units="m").write()

        # inverse kinematics for mot file
        opensim.InverseKinematicsTool().printToXML(f"{data_dir}/inverse_kin.xml")
        ik_input = f"{data_dir}/inverse_kin.xml"
        ik_output = f"{data_dir}/inverse_kin_out.xml"
        mot_output = f"{data_dir}/ik"
        pyosim.InverseKinematics(osim_model_path, ik_input, ik_output, trc_file, mot_output)
        import opensim as osim
        pyosim.Scale(model_input=osim_model_path,
                     model_output=model_output,
                     xml_input=scaling_tool,
                     xml_output=f'{data_dir}/scaling_tool_output.xml',
                     static_path=trc_file,
                     coordinate_file_name=f"{data_dir}/ik/anato.mot"
                     )

        # convert_model(in_path=f"{data_dir}/" + Path(model_output).stem + "_markers.osim",
        #               out_path=f"{data_dir}/" + Path(model_output).stem + '.bioMod', viz=False)
        convert_model(in_path=f"{data_dir}/" + Path(model_output).stem + "_markers.osim",
                      out_path=f"{data_dir}/" + Path(model_output).stem + '.bioMod', viz=False)

    else:
        # from pyomeca import Markers
        bmodel = biorbd.Model(model_path)
        # marker_names = []
        # for i in range(len(bmodel.markerNames())):
        #     marker_names.append(bmodel.markerNames()[i].to_string())
        # markers_full = Markers.from_c3d(f"data/test_18_11_21/gregoire/test_1/flex.c3d", usecols=marker_names)
        # marker_rate = int(markers_full.rate)
        # marker_exp = markers_full[:, :, :].data * 1e-3
        q_recons, _ = Server.kalman_func(markers, model=bmodel)
        b = bioviz.Viz(model_path=model_path)
        b.load_movement(q_recons)
        b.load_experimental_markers(markers)
        b.exec()


def convert_model(in_path, out_path, viz=None):
    #  convert_model
    from OsimToBiomod import Converter

    converter = Converter(out_path, in_path)
    converter.main()
    if viz:
        b = bioviz.Viz(model_path=out_path)
        b.exec()


if __name__ == '__main__':
    trial = "test_abd"
    subject = "Remi"
    data_dir = f"/home/amedeo/Documents/programmation/data_article/{subject}"
    # model_in = "/home/amedeo/Documents/programmation/data_article/Jules/Wu_Shoulder_Model_mod_wt_wrapp_Jules_scaled_with_mot.osim"
    # model_out = "/home/amedeo/Documents/programmation/data_article/Jules/Wu_Shoulder_Model_mod_wt_wrapp_Jules_scaled.bioMod"
    # model_in ="test_scale_mathis.osim"
    # model_out ="test_scale_mathis.bioMod"
    # convert_model(in_path=model_in, out_path=model_out, viz=True)
    # model_path = "data/test_09_12_21/Jules/Wu_Shoulder_Model_mod_wt_wrapp_Jules_scaled_with_mot.bioMod"
    model_path = f"{data_dir}/Wu_Shoulder_Model_mod_wt_wrapp_{subject}.osim"
    # model_path = f"{data_dir}/Wu_Shoulder_Model_mod_wt_wrapp_{subject}_scaled_test.bioMod"
    EKF(model_path, scaling=True, off_line=True)

