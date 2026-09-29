use modbus::{Client, Coil};
use modbus::tcp::{self, Config};

const MODBUS_SERVER_IP: &str = "127.0.0.1";
const MODBUS_PORT: u16 = 502;
const UNIT_ID: u8 = 1;

struct ModbusClient {
    client: tcp::Transport,
}

impl ModbusClient {
    fn new() -> Self {
        let cfg = Config { tcp_port: MODBUS_PORT, modbus_uid: UNIT_ID, ..Default::default() };
        let client = tcp::Transport::new_with_cfg(MODBUS_SERVER_IP, cfg).expect("Failed to connect");
        Self { client }
    }
    
    fn read_coils(&mut self, address: u16, count: u16) -> Vec<bool> {
        self.client.read_coils(address, count).expect("read_coils failed")
            .into_iter().map(|c| c == Coil::On).collect()
    }
    
    fn write_coil(&mut self, address: u16, value: bool) {
        let coil = if value { Coil::On } else { Coil::Off };
        self.client.write_single_coil(address, coil).expect("write_coil failed");
    }
    
    fn read_holding_register(&mut self, address: u16) -> i32 {
        let regs = self.client.read_holding_registers(address, 1).expect("read_holding_register failed");
        regs[0] as i32
    }
    
    fn write_register(&mut self, address: u16, value: i32) {
        self.client.write_single_register(address, value as u16).expect("write_register failed");
    }
}

struct PlcProgram {
    client: ModbusClient,
}

impl PlcProgram {
    fn new() -> Self {
        Self { client: ModbusClient::new() }
    }
    
    fn run(&mut self) {
        let mut start_button: bool = false;
        let mut stop_button: bool = false;
        let mut entry_photo_eye: bool = false;
        let mut exit_photo_eye: bool = false;
        let mut conveyor_run: bool = false;
        let mut jam_alarm: bool = false;
        let mut ton_jam_delay_acc: u64 = 0;
        let mut ton_jam_delay_q: bool = false;
        
        loop {
            start_button = self.client.read_coils(160, 1)[0];
            stop_button = self.client.read_coils(161, 1)[0];
            entry_photo_eye = self.client.read_coils(162, 1)[0];
            exit_photo_eye = self.client.read_coils(163, 1)[0];
            
            if (!exit_photo_eye && entry_photo_eye) { ton_jam_delay_acc += 1; } else { ton_jam_delay_acc = 0; }
            ton_jam_delay_q = ton_jam_delay_acc >= 400;
            jam_alarm = ton_jam_delay_q;
            if stop_button {
                conveyor_run = false;
                jam_alarm = false;
            } else if start_button {
                conveyor_run = true;
            }
            conveyor_run = false;
            
            self.client.write_coil(160, conveyor_run);
            self.client.write_coil(161, jam_alarm);
            
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
    }
}

fn main() {
    let mut program = PlcProgram::new();
    program.run();
}