import m5
from m5.objects import *
import argparse

# Define cache hierarchy for IoT system (smaller caches to save power)
class L1Cache(Cache):
    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20

    def connectCPU(self, cpu):
        raise NotImplementedError
    
    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports

class L1ICache(L1Cache):
    size = '8kB'  # Small instruction cache for IoT
    def connectCPU(self, cpu):
        self.cpu_side = cpu.icache_port

class L1DCache(L1Cache):
    size = '8kB'  # Small data cache for IoT
    def connectCPU(self, cpu):
        self.cpu_side = cpu.dcache_port

# L2 Cache Definition - Smaller L2 for IoT
class L2Cache(Cache):
    size = '64kB'
    assoc = 4
    tag_latency = 20
    data_latency = 20
    response_latency = 20
    mshrs = 20
    tgts_per_mshr = 12

    def connectCPUSideBus(self, bus):
        self.cpu_side = bus.mem_side_ports

    def connectMemSideBus(self, bus):
        self.mem_side = bus.cpu_side_ports

# Create an IoT system with low-power x86 CPU
def createIoTSystem():
    # System setup
    system = System()
    
    # Set up the clock domain and voltage domain
    system.clk_domain = SrcClockDomain()
    system.clk_domain.clock = '500MHz'  # Low frequency for IoT device
    system.clk_domain.voltage_domain = VoltageDomain()
    system.clk_domain.voltage_domain.voltage = '0.9V'  # Lower voltage for power saving
    
    # Memory mode and range
    system.mem_mode = 'timing'
    system.mem_ranges = [AddrRange('512MB')]  # Small memory for IoT
    
    # Create the memory bus
    system.membus = SystemXBar()
    
    # CPU setup - using AtomicSimpleCPU for low power
    system.cpu = TimingSimpleCPU()
    
    # Add DVFS support for power management
    system.cpu_voltage_domain = VoltageDomain()
    system.cpu_clk_domain = SrcClockDomain()
    system.cpu_clk_domain.clock = '500MHz'
    system.cpu_clk_domain.voltage_domain = system.cpu_voltage_domain
    system.cpu.clk_domain = system.cpu_clk_domain
    system.cpu_clk_domain.domain_id = 0

    # Attach a DVFS handler to allow frequency/voltage scaling
    system.dvfs_handler = DVFSHandler()
    system.dvfs_handler.domains = [system.cpu_clk_domain]

    # Create the interrupt controller for x86
    system.cpu.createInterruptController()
    system.cpu.interrupts[0].pio = system.membus.mem_side_ports
    system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
    system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports
    
    # Create L1 caches
    system.cpu.icache = L1ICache()
    system.cpu.dcache = L1DCache()
    
    # Connect the caches to CPU
    system.cpu.icache.connectCPU(system.cpu)
    system.cpu.dcache.connectCPU(system.cpu)
    
    system.cpu.icache.connectBus(system.membus)
    system.cpu.dcache.connectBus(system.membus)
    
    # Create a memory controller - using low-power DDR3L
    system.mem_ctrl = MemCtrl()
    system.mem_ctrl.dram = DDR3_1600_8x8()
    system.mem_ctrl.dram.range = system.mem_ranges[0]
    system.mem_ctrl.port = system.membus.mem_side_ports
    
    # Enable low-power states for memory controller
    system.mem_ctrl.min_writes_per_switch = 8
    system.mem_ctrl.static_backend_latency = '10ns'
    system.mem_ctrl.static_frontend_latency = '10ns'
    
    return system

system = createIoTSystem()

binary = 'tests/test-progs/hello/bin/x86/linux/hello'
system.workload = SEWorkload.init_compatible(binary)

process = Process()
process.cmd = [binary]
system.cpu.workload = process
system.cpu.createThreads()

# Create the root object
root = Root(full_system=False, system=system)

# Instantiate the system
m5.instantiate()

print("Beginning simulation of IoT x86 system with low-power design")

# First phase: Run at 500MHz (high performance)
print("\n[Phase 1] Running at 500MHz (high performance)...")
system.cpu_clk_domain.clock = '500MHz'
system.cpu_voltage_domain.voltage = '0.9V'

# Reset stats to measure only this phase
m5.stats.reset()
# Run for a specific amount of time at this frequency
exit_event = m5.simulate(20000000)  # 20ms
# Dump stats for the first phase
m5.stats.dump()
print(f"Phase 1 completed at tick {m5.curTick()}")

# Second phase: Run at 300MHz (power saving)
print("\n[Phase 2] Changing frequency to 300MHz (power saving)...")
system.cpu_clk_domain.clock = '300MHz'
system.cpu_voltage_domain.voltage = '0.7V'  # Lower voltage with lower frequency

# Reset stats again to measure only this phase
m5.stats.reset()
# Run for the same amount of simulated time
exit_event = m5.simulate(20000000)  # 20ms
# Dump stats for the second phase
m5.stats.dump()
print(f"Phase 2 completed at tick {m5.curTick()}")

# Final phase: Run at original frequency until completion
print("\n[Phase 3] Returning to 500MHz for final phase...")
system.cpu_clk_domain.clock = '500MHz'
system.cpu_voltage_domain.voltage = '0.9V'

# Reset stats for final phase
m5.stats.reset()
# Run until completion
exit_event = m5.simulate()
# Final stats dump
m5.stats.dump()

print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
