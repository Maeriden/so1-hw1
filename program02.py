class ClockSlot:
    def __init__(self, page):
        self.skip = False
        self.page = page
        
class Clock:
    def __init__(self, slot_count):
        self.index = 0
        self.slots = [ClockSlot(None) for _ in range(slot_count)]
    
    
    def set_page(self, slot, page):
        assert slot < len(self.slots)
        self.slots[slot].page = page
        self.slots[slot].skip = True
    
    def set_used(self, page):
        assert page in [slot.page for slot in self.slots]
        for slot in self.slots:
            if slot.page == page:
                slot.skip = True


class MemorySimulator:
    def __init__(self, total_memory_size, user_memory_size, secondary_memory_size, page_size, frame_requirements):
        self.total_memory_size     = total_memory_size
        self.user_memory_size      = user_memory_size
        self.secondary_memory_size = secondary_memory_size
        self.page_size             = page_size
        self.frame_requirements    = frame_requirements
        
        self.user_memory_ptr = self.total_memory_size - self.user_memory_size
        self.user_memory = [(None, proc) for proc, reqs in enumerate(frame_requirements) for _ in range(reqs)]
        self.clocks = [Clock(reqs) for reqs in frame_requirements]
        
        self.page_hits   = [0 for _ in frame_requirements]
        self.page_misses = [0 for _ in frame_requirements]
    

    def handle_request(self, logic_address, process_index):
        address_page = logic_address // self.page_size
        address_offs = logic_address % self.page_size
        
        frame = None
        # Search page in available frames
        for i, (page, proc) in enumerate(self.user_memory):
            if proc == process_index:
                if page == address_page:
                    frame = i
                    break
        
        clock = self.clocks[process_index]
        
        if frame is not None:
            assert address_page in [slot.page for slot in clock.slots]
            # Mark the page used (skippable)
            for slot in clock.slots:
                if slot.page == address_page:
                    slot.skip = True
            self.page_hits[process_index] += 1
        else:
            # Search the frame where this process memory begins
            process_frames_begin = 0
            while self.user_memory[process_frames_begin][1] != process_index:
                process_frames_begin += 1
            
            # Search for evictable page (clock slot)
            while clock.slots[clock.index].skip:
                clock.slots[clock.index].skip = False
                clock.index = (clock.index+1) % len(clock.slots)
            
            # Compute evictable frame global index
            frame = process_frames_begin + clock.index

            # Substitute page frame
            clock.slots[clock.index].page = address_page
            clock.slots[clock.index].skip = True
            clock.index = (clock.index+1) % len(clock.slots)
            
            self.user_memory[frame] = (address_page, process_index)
            self.page_misses[process_index] += 1
            
            
        frame_address      = frame * self.page_size
        real_frame_address = self.user_memory_ptr + frame_address
        physical_address   = real_frame_address + address_offs
        return (frame, physical_address)
    

    def get_memory(self):
        return self.user_memory
    
    def get_stats(self):
        return (self.page_hits, self.page_misses)
