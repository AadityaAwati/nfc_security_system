import os
import zipfile

import serial
import threading

import tkinter as tk
import pygame

import pandas

from flask import Flask, render_template, send_from_directory, send_file, jsonify, request

import cv2
from datetime import datetime, date

camera = cv2.VideoCapture(0)

camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

app = Flask(__name__)
stop_data_send = True


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/submit_date', methods=['POST'])
def submit_date():
    js_data = request.json
    selected_date = js_data.get('date')

    if not selected_date:
        return jsonify({"error": "No date provided"}), 400

    selected_date_parts = selected_date.split("-")
    proper_date = f"{selected_date_parts[2]}-{selected_date_parts[1]}-{selected_date_parts[0]}"

    for file in os.listdir("Records"):
        if proper_date == file.split("_")[1].split(".")[0] and file.endswith('.csv'):
            file_path = os.path.join("Records", file)
            return send_file(file_path, as_attachment=True, download_name=file, mimetype='text/csv')

    return jsonify({"error": "File not found for the selected date"}), 404


@app.route('/restricted_range', methods=['GET'])
def get_restricted_range():
    all_record_dates = os.listdir("Records")
    record_dates_totaled = []

    for record_date in all_record_dates:
        day = int(record_date.split("-")[0].split("_")[1])
        month = int(record_date.split("-")[1]) * 100
        year = int(record_date.split("-")[2].split(".")[0])

        record_dates_totaled.append(day + month + year)

    first_totaled_date = min(record_dates_totaled)
    last_totaled_date = max(record_dates_totaled)

    first_date = all_record_dates[record_dates_totaled.index(first_totaled_date)].split("_")[1].split(".")[0].split("-")
    last_date = all_record_dates[record_dates_totaled.index(last_totaled_date)].split("_")[1].split(".")[0].split("-")

    start_date = date(int(first_date[2]), int(first_date[1]), int(first_date[0]))
    end_date = date(int(last_date[2]), int(last_date[1]), int(last_date[0]))

    return jsonify({
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    })


@app.route('/download_folder')
def download_folder():
    folder_path = 'Records'
    zip_file_path = 'Records.zip'

    with zipfile.ZipFile(zip_file_path, 'w') as zip_file:
        for root_, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root_, file)

                arc_name = os.path.relpath(file_path, folder_path)
                zip_file.write(file_path, arc_name)

    return send_file(zip_file_path, as_attachment=True)


@app.route('/Images/<path:filename>')
def serve_file(filename):
    directory = 'static/Images'
    return send_from_directory(directory, filename)


@app.route('/data')
def send_data():
    if data:
        data_to_be_sent = {'message': data}
    else:
        data_to_be_sent = {'message': []}

    global stop_data_send

    if not stop_data_send:
        stop_data_send = True
        return data_to_be_sent
    else:
        return {'message': []}


data = []

arduino = serial.Serial('COM6', 115200, timeout=1)

current_date = datetime.now().strftime("%d-%m-%Y")
record_file_name = f"record_{current_date}"

if os.path.exists(f"Records/{record_file_name}.csv"):
    record = pandas.read_csv(f"Records/{record_file_name}.csv").to_dict()
    modified_record = {}

    for key in record:
        modified_record[key] = []
    for key_ in record:
        for index in record[key_]:
            modified_record[key_].append(record[key_][index])

    record = modified_record
else:
    record = {
        "Card UID": [],
        "Time": [],
        "Is Authorized": []
    }
    record_dataframe = pandas.DataFrame(record)
    os.makedirs("Records", exist_ok=True)
    record_dataframe.to_csv(f"Records/{record_file_name}.csv")

main_access_card = " 0xF3 0xF 0x26 0xF"

root = tk.Tk()
root.title("Advanced RFID Door Lock System")
root.geometry("1600x820")
root.config(background="black")

label = tk.Label(text="Ready to Read Card !!", fg="white", font=("", 30, "bold"), bg="black")
label.place(x=600, y=350)


def run_http_server():
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=5000, debug=False)


def update_label(text, color="white"):
    label.config(text=text, fg=color)
    label.update()


def while_loop():
    global stop_data_send

    try:
        while True:
            _, frame = camera.read()

            data_received = arduino.readline().decode("utf-8").strip()
            print(data_received)

            if "UID Value: " in data_received:

                data_received = data_received.split("UID Value: ")[1]
                current_time = datetime.now().strftime("%H:%M")

                stop_data_send = False

                print(f"Card Scanned: {data_received}")

                current_date_time = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
                image_file_name = "static/Images/" + current_date_time + ".jpg"

                cv2.imwrite(image_file_name, frame)

                record["Card UID"].append(data_received)
                record["Time"].append(current_time)

                if data_received == main_access_card:
                    record["Is Authorized"].append("True")

                    if data:
                        data[0] = f"/Images/{current_date_time}.jpg,{data_received},{current_time},True"
                    else:
                        data.append(f"/Images/{current_date_time}.jpg,{data_received},{current_time},True")

                    arduino.write(bytes("1", "utf-8"))
                    root.after(0, update_label,
                               "Authorized Entry!/nDoor will automatically close in 5 seconds", "green")
                    pygame.mixer.init()
                    pygame.mixer.music.load("access_authorized.mp3")
                    pygame.mixer.music.play()
                    root.after(5000, update_label, "Ready to Read Card !!", "white")
                else:
                    record["Is Authorized"].append("False")

                    if data:
                        data[0] = f"/Images/{current_date_time}.jpg,{data_received},{current_time},False"
                    else:
                        data.append(f"/Images/{current_date_time}.jpg,{data_received},{current_time},False")

                    arduino.write(bytes("0", "utf-8"))
                    root.after(0, update_label, "Access Denied.", "red")
                    pygame.mixer.init()
                    pygame.mixer.music.load("access_denied.mp3")
                    pygame.mixer.music.play()
                    root.after(3000, update_label, "Ready to Read Card !!", "white")

                if "Unnamed: 0" in list(record.keys()):
                    del record["Unnamed: 0"]

                record_df = pandas.DataFrame(record)
                record_df.to_csv(f"Records/{record_file_name}.csv", index=False)

    except KeyboardInterrupt:
        arduino.close()


http_thread = threading.Thread(target=run_http_server, daemon=True)
http_thread.start()

main_program = threading.Thread(target=while_loop, daemon=True)
main_program.start()

root.mainloop()
