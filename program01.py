import sys


ALMOST_ZERO = 1e-5


class ProcInfo:
	def __init__(self, pid, ops):
		self.pid = pid
		self.ops = ops # Sarebbe code_io[]

	def schifo(self):
		"""Ritorna l'array dei tempi mappando a 0.0 i tempi negativi"""
		return [max(0.0, op) for op in self.ops]


class SchedulerState:
	def __init__(self):
		self.kill_running_process     = False
		self.pause_running_process    = False
		self.block_running_process    = False
		self.handle_blocked_processes = False
		self.run_new_process          = False


class SchedulerSimulator:
	def __init__(self, quantum, max_procs):
		"""`quantum` e il quanto di tempo (in secondi) e
`max_procs` e il numero massimo di processi che possono essere accettati
dallo scheduler. Si può assumere che, una volta settati, quantum e
max procs non vengano mai cambiati. Il tempo interno del simulatore
va settato a 0."""

		# Quanto tempo di CPU resta al processo running
		self.remaining_quantum = 0.0
		
		# Quanto di tempo. Usato per resettare remaining_quantum
		self.quantum   = quantum
		
		# PID disponibili per nuovi processi
		self.free_pids = list(range(1, max_procs+1))
		
		self.queue_ready   = []
		self.queue_blocked = []
		self.running_proc  = None
		
	
	def advance_time(self, delta_time):
		"""Avanza il tempo del simulatore di t secondi (da notare
che potrebbe dover eseguire zero, uno o più context switch). Assumere che
tutte le operazioni di I/O possano essere eseguite in parallelo (ad esempio
perchè vengono fatte su dispositivi diversi)."""

		# `breaker` serve solo a tirare un assert nel caso di un bug che causa un ciclo infinito
		# In questa versione del codice non succede mai.
		breaker = 1000
		
		# Esegui finchè rimane tempo da avanzare
		while delta_time > ALMOST_ZERO:
			
			# Il running va ucciso se gli rimane una sola operazione (che sara' di CPU) nella lista e quella operazione
			# ha finito di fare il suo lavoro
			if self.running_proc:
				if len(self.running_proc.ops) == 1 and self.running_proc.ops[0] < ALMOST_ZERO:
					self.kill_running_process() # Imposta running_proc a None
			
			# Il running va messo in ready se non è stato ucciso e il quanto assegnatogli è scaduto
			if self.running_proc:
				if self.remaining_quantum < ALMOST_ZERO:
					self.pause_running_process() # Imposta running_proc a None
			
			# Il running va bloccato se non è stato ucciso, non è stato messo ready, e se l'operazione corrente
			# ha finito di fare il suo lavoro (cioè è arrivata a zero)
			if self.running_proc:
				if self.running_proc.ops[0] < ALMOST_ZERO:
					self.block_running_process() # Imposta running_proc a None
			
			
			# I blocked vanno gestiti in TUTTI i casi in cui è necessario scegliere un nuovo processo running.
			# Vedere il prossimo commento per le condizioni di selezione di un nuovo running.
			if not self.running_proc:
						
				# Caso speciale per quando non restano processi ready (questa cosa non ha senso ma mi passare due test in più)
				threshold = -ALMOST_ZERO if self.queue_ready else ALMOST_ZERO
				# threshold = ALMOST_ZERO
				
				# Cicla su una copia dell'array dei blocked perchè durante il ciclo l'array può essere modificato
				for blocked in self.queue_blocked[:]:
					if blocked.ops[0] < threshold:
						self.ready_blocked_process(blocked)
			
			
			# Se si arriva a questo punto della simulazione e non c'è un running, bisogna sceglierne uno nuovo
			# L'assenza di un running succede in 5 casi:
			# 1) All'inizio della simulazione (running_proc viene inizializzato a None)
			# 2) Il running è stato appena ucciso (running_proc viene impostato a None)
			# 3) Il running è stato appena pausato (running_proc viene impostato a None)
			# 4) Il running è stato appena bloccato (running_proc viene impostato a None)
			# 5) Un ciclo precedente non è riuscito a trovare un running valido tra i ready
			#    In questo caso la simulazione ha fatto avanzare il tempo finchè un blocked non finisce il suo tempo
			#    di IO, che quindi sarà appena stato spostato nei ready, pronto per andare in running)
			if not self.running_proc:
				
				# Si prende il processo in testa alla coda dei ready e lo si mette running.
				# Può succedere che in una simulazione precedente il tempo di CPU di questo processo era arrivato
				# "esattamente" a 0.0. Ciò non era sufficiente per bloccare il processo, ma se andasse in esecuzione
				# adesso supererebbe subito lo zero, quindi lo si blocca.
				# Questa operazione viene ripetuta finchè non si è trovato un running "valido" e rimangono dei
				# candidati nella coda dei ready.
				while not self.running_proc and self.queue_ready:
					self.run_next_process()
					if self.running_proc.ops[0] < ALMOST_ZERO:
						self.block_running_process() # Imposta running_proc a None
			
				# Se è stato trovato un running "valido", si resetta il tempo assegnatogli
				if self.running_proc:
					self.remaining_quantum = self.quantum
				
			
			############################################################################################################
			## Dopo avere controllato e impostato lo stato dello scheduler
			## (quale processo è in running, gestione dei blocked, ecc), avanziamo il tempo
			############################################################################################################
			
			# `timestep` indica quanto avanza il tempo in questa iterazione del while
			timestep = 0
			
			# Se c'è un processo running, bisogna avanzare fino al prossimo "evento", uno tra:
			# - Avanza di delta_time: è scaduto il tempo assegnato a questa chiamata di advance_time(). Aggiorniamo i
			#   contatori dei processi e usciamo dal ciclo e funzione
			# - Avanza di remaining_quantum: è scaduto il quanto assegnato al running. Aggiorniamo i contatori e
			#   ricominciamo il ciclo in modo che il running possa essere messo in ready e un nuovo running venga scelto
			# - Avanza di running.code_io[0]: è scaduto il tempo di CPU del running. Aggiorniamo i contatori e
			#   ricominciamo il ciclo in modo che il running possa essere bloccato e un nuovo running venga scelto
			
			# Nel secondo e terzo caso (prendiamo come esempio il terzo), se delta_time == running.code_io[0],
			# succederà che il ciclo non esegue un'altra iterazione (perchè timestep viene sottratto a delta_time).
			# Questo va bene perchè running.code_io[0] diventerà UGUALE a zero, ma non lo supera, quindi il running
			# non va ancora spostato nei blocked.
			# Uscendo dalla funzione il grader riporterà il running come ancora running con un tempo di 0.0
			
			# Alla successiva chiamata di advance_time(), lo stato dello scheduler noterà che running.code_io[0] == 0.0
			# Dato che lo stato viene controllato all'inizio del ciclo, si può assumere che si sta per avanzare il tempo,
			# ovvero che running.code_io[0] è in procinto di andare sotto zero, quindi lo scheduler può bloccare il running
			if self.running_proc:
				timestep = min(delta_time, self.remaining_quantum, self.running_proc.ops[0])
			else:
				# La coda dei bloccati e' vuota oppure ogni operazione ha tempo maggiore di 0
				assert not self.queue_blocked or not [b for b in self.queue_blocked if b.ops[0] < ALMOST_ZERO]
				
				# Se non c'era un processo running bisogna avanzare il tempo finchè uno dei blocked non torna ready
				# Quindi scegliamo il tempo da avanzare tra:
				# - delta_time: se nessun blocked finisce prima che scada il tempo allocato a qeusta chiamata di advance_time()
				#   bisogna avanzare il tempo di delta_time e uscire da ciclo e funzione
				# - Il più piccolo tempo di attesa tra i blocked: appena uno arriva a zero, avanza il tempo e ricomincia 
				#   il ciclo, così che uno dei blocked possa venire spostato nei ready e poi in running
				
				# In questo scenario è garantito che blocked.code_io[0] > 0.0 per ogni blocked, perchè l'assenza di un
				# running causa la gestione dei blocked, quindi tutti quelli con tempo <= 0.0 sono stati messi in ready
				
				# NOTA: L'argomento di min() dipende da una limitazione pratica su come min() accetta argomenti
				# È semplicemente un array con tutti i code_io[0] dei blocked (se esistono) più delta_time
				# Come dire min(delta_time, blocked[0].code_io[0], blocked[1].code_io[0], ...)
				timestep = min([delta_time] + [b.ops[0] for b in self.queue_blocked])
			
			
			# Avanza il tempo aggiornando i contatori dei processi
			assert timestep > 0, "SchedulerSimulator.advance_time(): timestep = 0"
			if self.running_proc:				
				self.running_proc.ops[0] -= timestep
			for blocked in self.queue_blocked:
				blocked.ops[0] -= timestep
				
			
			# Sottrai il tempo avanzato da quello rimanente
			self.remaining_quantum -= timestep
			delta_time             -= timestep
			
			
			# Aggiorna preaker in modo da spaccare cicli infiniti
			breaker -= 1
			assert breaker > 0, "SchedulerSimulator.advance_time(): Infinite loop"

	
	def add_proc(self, code_io):
		"""Aggiunge un nuovo processo (come ready), nell’attuale
tempo del simulatore. L’argomento `code_io` e una lista di
tempi di esecuzione [t0 ,...,tn−1 ], tali che ogni ti indica per quanto tempo
verrà eseguito il processo prima di arrivare alla prossima istruzione di I/O
se i è pari, mentre indica quanto il device di I/O impiega per servire
l’attuale operazione di I/O se i è dispari. Questo metodo deve tornare
un pid per il processo, inteso come numero intero tra 1 e `max_procs`. Se
ci sono già `max_procs` processi che competono per l’esecuzione, questo
metodo deve tornare None, senza aggiungere il processo."""
		if not self.free_pids:
			return None
		pid = min(self.free_pids)
		self.free_pids.remove(pid)

		proc = ProcInfo(pid, code_io)
		self.queue_ready.append(proc)
		return proc.pid
	
	
	def get_ready(self):
		"""Ritorna la lista dei processi attualmente nella coda dei pro-
cessi ready, dove ogni elemento della lista è un dizionario con 2 chiavi:
pid e code_io. L’ordinamento della lista dev’essere quello dell’attuale
coda dei ready: ovvero, al posto 0 c'è l’elemento che si trova sul fronte
della coda (ciò che verrebbe estratto per primo), al posto 1 il secondo e
così via. Ovviamente, rispetto a quello indicato con add_proc, il code_io
dev’essere opportunamente modificato tenendo conto dell’avanzamento del
tempo (ovvero, delle chiamate ad advance_time)."""
		return [ {"pid": proc.pid, "code_io": proc.ops} for proc in self.queue_ready ]
	
	
	def get_blocked(self):
		"""Ritorna la lista dei processi blocked al tempo attuale, con lo
stesso formato di get_ready()"""
		# return [ {"pid": proc.pid, "code_io": proc.ops} for proc in self.queue_blocked ]
		return [ {"pid": proc.pid, "code_io": proc.schifo()} for proc in self.queue_blocked ]
	
		
	def get_running(self):
		"""ritorna il processo attualmente in esecuzione, sempre come
dizionario con chiavi pid e code_io; se nessun processo è attualmente
in esecuzione, allora deve tornare None."""
		return {"pid": self.running_proc.pid, "code_io": self.running_proc.ops} if self.running_proc else None
	
	
	def get_scheduler_state(self):
		state = SchedulerState()
		
		# Il running va ucciso se gli rimane una sola operazione (che sara' di CPU) nella lista e quella operazione
		# ha finito di fare il suo lavoro
		## kill_running_process
		if self.running_proc:
			if len(self.running_proc.ops) == 1 and self.running_proc.ops[0] < ALMOST_ZERO:
				state.kill_running_process = True
		
		# Il running va messo in ready se non deve essere ucciso e il quanto assegnatogli è scaduto
		## pause_running_process
		if self.running_proc:
			if not state.kill_running_process:
				if self.remaining_quantum < ALMOST_ZERO:
					state.pause_running_process = True
		
		# Il running va bloccato se non deve essere ucciso, non deve essere messo ready, e se l'operazione corrente
		# ha finito di fare il suo lavoro (cioè è arrivata a zero)
		## block_running_process
		if self.running_proc:
			if not state.kill_running_process:
				if not state.pause_running_process:
					if self.running_proc.ops[0] < ALMOST_ZERO:
						state.block_running_process = True
		
		# Va scelto un nuovo processo ready se proprio non ce n'era uno, oppure se quello che c'è sta per essere
		# ucciso/pausato/bloccato
		## run_new_process
		if not self.running_proc:
			state.run_new_process = True
		if state.kill_running_process:
			state.run_new_process = True
		if state.pause_running_process:
			state.run_new_process = True
		if state.block_running_process:
			state.run_new_process = True
		
		# I bloccati vanno gestiti in tutti quei casi che causano un cambio di running
		# Equivalente a state.handle_blocked_processes = state.run_new_process
		## handle_blocked_processes
		if not self.running_proc:
			state.handle_blocked_processes = True
		if state.kill_running_process:
			state.handle_blocked_processes = True
		if state.pause_running_process:
			state.handle_blocked_processes = True
		if state.block_running_process:
			state.handle_blocked_processes = True
		
		return state
	
	
	def kill_running_process(self):
		"""Rilascia il PID assegnato al processo running e imposta che non
c'e' un running.
Causa errore se non c'e' un running o se non ha terminato l'esecuzione."""
		assert self.running_proc, "SchedulerSimulator.kill_running_process(): There is no running process"
		assert len(self.running_proc.ops) == 1, "SchedulerSimulator.kill_running_process(): Running process still has operations"
		assert self.running_proc.ops[0] <= ALMOST_ZERO, "SchedulerSimulator.kill_running_process(): Running process has not finished yet"
		
		self.free_pids.append(self.running_proc.pid)
		self.running_proc = None
	
	
	def pause_running_process(self):
		"""Sposta il processo running nella coda dei ready.
Causa errore se non c'e' un running o se il tempo assegnatogli non e'
scaduto."""
		assert self.running_proc, "SchedulerSimulator.pause_running_process(): There is no running process"
		assert self.remaining_quantum < ALMOST_ZERO, "SchedulerSimulator.pause_running_process(): Quantum has not expired yet"
		
		self.queue_ready.append(self.running_proc)
		self.running_proc = None
	
	
	def block_running_process(self):
		"""Sposta il processo running nella coda dei blocked, rimuovendo
il tempo di CPU in testa alla sua lista di operazioni.
Causa errore se non c'e' un running o se il tempo di CPU in testa alla
lista non e' scaduto."""
		assert self.running_proc, "SchedulerSimulator.block_running_process(): There is no running process"
		assert self.running_proc.ops[0] < ALMOST_ZERO, "SchedulerSimulator.block_running_process(): Running process has not finished yet"
		
		self.queue_blocked.append(self.running_proc)
		self.running_proc.ops.pop(0)
		self.running_proc = None
	
	
	def ready_blocked_process(self, proc):
		"""Sposta un processo dalla coda dei blocked nella coda dei ready,
rimuovendo il tempo di IO in testa alla sua lista di operazioni.
Causa errore se il processo non era nella coda dei blocked o se il tempo
di IO in testa alla lista non e' scaduto."""
		assert proc in self.queue_blocked, "SchedulerSimulator.ready_blocked_process(): Process is not blocked"
		assert proc.ops[0] < ALMOST_ZERO, "SchedulerSimulator.ready_blocked_process(): Process has not finished yet"
		
		self.queue_blocked.remove(proc)
		self.queue_ready.append(proc)
		proc.ops.pop(0)
	
	
	def run_next_process(self):
		"""Imposta il processo in testa alla coda dei ready come running.
Causa errore se c'e' gia' un running o se la coda dei ready e' vuota."""
		assert not self.running_proc, "SchedulerSimulator.run_next_process(): There is already a running process"
		assert len(self.queue_ready) > 0, "SchedulerSimulator.run_next_process(): There are no ready processes"
		
		self.running_proc = self.queue_ready.pop(0)
