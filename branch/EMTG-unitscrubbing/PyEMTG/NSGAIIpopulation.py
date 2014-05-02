#tool for reading NSGA-II population and archive files
#for use with EMTG-NSGAII outer-loop by Vavrina and Englander
#Python interface by Jacob Englander begun 3-16-2014

import os
import numpy as np
from scipy.integrate import ode
import matplotlib
import pylab
from mpl_toolkits.mplot3d import Axes3D
import copy

class NSGAII_outerloop_solution(object):
    
    #constructor
    def __init__(self, input_line, column_headers):
        self.initialize()
        self.parse_input_line(input_line, column_headers)

    #clear function
    def initialize(self):
        self.Xouter = [] #outer-loop decision vector
        self.Xinner = [] #inner-loop decision vector
        self.objective_values = [] #vector of objective function values
        self.power_system_size = [] #if applicable, power level of the array in kW
        self.thruster = []
        self.number_of_thrusters = []
        self.launch_vehicle = []
        self.launch_date = []
        self.description = [] # case name, can be parsed for data
        self.mission_sequence = []
        self.generation_found = [] #what generation was this solution found?
        self.timestamp = [] #at what time, in seconds from program start, was this solution found?

    #line parser
    def parse_input_line(self, input_line, column_headers):
        #strip off the newline character
        input_line = input_line.strip("\n")

        #strip the input line by commas
        input_cell = input_line.split(',')

        #declare arrays of launch vehicle and thruster names
        LV_names = ['AV401','AV411','AV421','AV431','AV501','AV511','AV521','AV531','AV541','AV551',
                    'F910','F911','AV551s48','F9H','D4H','SLSb1']
        thruster_names = ['NSTAR','XIPS25','BPT4000HIsp','BPT4000Hthrust','BPT4000XHIsp',
                          'NEXTHIspv9','VASIMRargon','VSIxenonhall','NEXTHIspv10','NEXTHthrustv10',
                          'BPT4000MALTO','NEXIS','H6MS','BHT20K','HiVHAc']

        for column_index in range(0, len(column_headers)):
            if column_headers[column_index] == 'Generation found':
                self.generation_found = int(input_cell[column_index])

            elif column_headers[column_index] == 'timestamp':
                self.timestamp = int(input_cell[column_index])
            
            elif column_headers[column_index] == 'Description':
                self.description = input_cell[column_index]

                #find the mission sequence descriptor
                left_parenthesis_index = self.description.find('(')
                self.mission_sequence = self.description[left_parenthesis_index+1:].strip(')')
                
                #reconstruct the full mission description from the case name
                descriptioncell = self.description.split('_')

                for descriptionitem in descriptioncell:
                    if descriptionitem.find('kW') > 0: #this entry encodes power system size
                        self.power_system_size = float(descriptionitem.strip('kW'))

                    if descriptionitem.find('nTh') > 0:
                        self.number_of_thrusters = descriptionitem.strip('nTh')

                    for LV_name in LV_names:
                        if descriptionitem == LV_name:
                            self.launch_vehicle = descriptionitem

                    for thruster_name in thruster_names:
                        if descriptionitem == thruster_name:
                            self.thruster = thruster_name

            elif column_headers[column_index] == 'BOL power at 1 AU (kW)' \
                or column_headers[column_index] == 'Launch epoch (MJD)' \
                or column_headers[column_index] == 'Flight time (days)' \
                or column_headers[column_index] == 'Thruster preference' \
		        or column_headers[column_index] == 'Number of thrusters' \
		        or column_headers[column_index] == 'Launch vehicle preference' \
		        or column_headers[column_index] == 'Final journey mass increment (for maximizing sample return)' \
                or column_headers[column_index] == 'First journey departure C3 (km^2/s^2)' \
                or column_headers[column_index] == 'Final journey arrival C3 (km^2/s^2)' \
                or column_headers[column_index] == 'Total delta-v (km/s)':
                #this entry is an objective function value
                self.objective_values.append(float(input_cell[column_index]))
            elif column_headers[column_index] == 'Delivered mass to final target':
                self.objective_values.append(-float(input_cell[column_index]))

            elif column_headers[column_index].find('Gene ') > 0:
                self.Xouter.append(int(input_cell[column_index]))

            elif input_cell[column_index] != '': #this entry is a member of the inner-loop decision vector
                self.Xinner.append(float(input_cell[column_index]))


#top-level container of NSGAII_outerloop_solution objects
class NSGAII_outerloop_population(object):
        
    #constructor
    def __init__(self, population_file_name):
        self.clear()
        self.parse_population_file(population_file_name)

    def clear(self):
        self.solutions = [] #vector of NSGAII_outerloop_solution objects
        self.global_column_headers = []
        self.gene_column_headers = []
        self.objective_column_headers = []
        self.number_of_feasible_solutions = []
        self.points_array = []

    #method to read a population file
    def parse_population_file(self, population_file_name):
        #Step 1: attempt to open a population file
        if os.path.isfile(population_file_name):
            inputfile = open(population_file_name, "r")
            self.success = 1
        else:
            print "Unable to open", population_file_name, "EMTG Error"
            self.success = 0
            return

        #Step 2: scan through the file
        linenumber = 0
        for line in inputfile:
            #strip off the newline character
            line = line.replace("\n","")
            linenumber = linenumber + 1

            #the fourth line of the population file contains the column headers
            if linenumber == 4:
               self.global_column_headers = line.split(',')
               for header in self.global_column_headers:
                if header == 'BOL power at 1 AU (kW)' \
                    or header == 'Launch epoch (MJD)' \
                    or header == 'Flight time (days)' \
                    or header == 'Thruster preference' \
                    or header == 'Number of thrusters' \
                    or header == 'Launch vehicle preference' \
                    or header == 'Delivered mass to final target' \
                    or header == 'Final journey mass increment (for maximizing sample return)' \
                    or header == 'First journey departure C3 (km^2/s^2)' \
                    or header == 'Final journey arrival C3 (km^2/s^2)' \
                    or header == 'Total delta-v (km/s)':
                    self.objective_column_headers.append(header)

            #the fifth line of the population file contains the gene names
            elif linenumber == 5:
                self.gene_column_headers = line.split(',')

            #every line after the fifth is a solution line
            elif linenumber > 5:
                tempSolution = NSGAII_outerloop_solution(line, self.global_column_headers)
                self.solutions.append(tempSolution)

    #method to plot the population
    #input is an ordered list of objectives, [x, y, z, color]. If there are two objectives, a monochrome 2D plot will be shown. If there are three objectives, a monochrome 3D plot will be shown.
    #if there are four, a colored 3D plot will be shown. If there are more than four there will be an error message.
    def plot_population(self, ordered_list_of_objectives):
        #first check to see if the correct number of objective function indices were supplied
        if len(ordered_list_of_objectives) < 2 or len(ordered_list_of_objectives) > 4:
            print "NSGAII_outerloop_population::plot_population ERROR. You must specify between two and four objective functions to plot."
            return

        self.PopulationFigure = matplotlib.pyplot.figure()
        self.PopulationFigure.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.99)
        if len(ordered_list_of_objectives) == 2:
            self.PopulationAxes = self.PopulationFigure.add_subplot(111, projection='2d')
        else:
            self.PopulationAxes = self.PopulationFigure.add_subplot(111, projection='3d')
        
        self.PopulationAxes.set_xlabel(self.objective_column_headers[ordered_list_of_objectives[0]])
        self.PopulationAxes.set_ylabel(self.objective_column_headers[ordered_list_of_objectives[1]])
        if len(ordered_list_of_objectives) > 2:
            self.PopulationAxes.set_zlabel(self.objective_column_headers[ordered_list_of_objectives[2]])
            self.PopulationAxes.autoscale_view(tight=True, scalex=True, scaley=True, scalez=True)
        else:
            self.PopulationAxes.autoscale_view(tight=True, scalex=True, scaley=True)
        self.PopulationAxes.grid(b=True)

        #build up a list of objective values to be plotted
        self.objective_values_matrix = []
        for objective_index in range(0, len(ordered_list_of_objectives)):
            objective_values_vector = []
            for solution in self.solutions:
                if max(solution.objective_values) < 1.0e+99:
                    objective_values_vector.append(copy.deepcopy(solution.objective_values[objective_index]))
            self.objective_values_matrix.append(np.array(objective_values_vector))

        #determine upper and lower bounds on each objective
        self.upperbounds = []
        self.lowerbounds = []
        for objective_index in range(0, len(ordered_list_of_objectives)):
            self.upperbounds.append(self.objective_values_matrix[objective_index].max())
            self.lowerbounds.append(self.objective_values_matrix[objective_index].min())

        #plot each solution
        self.plot_solution_points(ordered_list_of_objectives)

        self.PopulationFigure.show()

    def plot_solution_points(self, ordered_list_of_objectives):
        self.colorbar = None
        self.solution_names = []
        for solution in self.solutions:
            if max(solution.objective_values) < 1.0e+99:
                self.solution_names.append(solution.description)
                if len(ordered_list_of_objectives) == 2: #2D
                    self.point = self.PopulationAxes.scatter(solution.objective_values[ordered_list_of_objectives[0]], solution.objective_values[ordered_list_of_objectives[1]], s=20, c='b', marker='o', lw=0, picker=5)
                elif len(ordered_list_of_objectives) == 3: #3D
                        self.point = self.PopulationAxes.scatter(solution.objective_values[ordered_list_of_objectives[0]], solution.objective_values[ordered_list_of_objectives[1]], solution.objective_values[ordered_list_of_objectives[2]], s=20, c='b', marker='o', lw=0, picker=5)
                else: #4D
                    if self.colorbar is None:
                        self.point = self.PopulationAxes.scatter(solution.objective_values[ordered_list_of_objectives[0]], solution.objective_values[ordered_list_of_objectives[1]], solution.objective_values[ordered_list_of_objectives[2]], s=20, c=solution.objective_values[ordered_list_of_objectives[4]], marker='o', lw=0, picker=5)
                        self.point.set_clim([self.lowerbounds[-1],self.upperbounds[-1]])
                        self.colorbar = self.PopulationFigure.colorbar(self.point)
                    else:
                        self.point = plotaxes.scatter(solution.objective_values[ordered_list_of_objectives[0]], solution.objective_values[ordered_list_of_objectives[1]], solution.objective_values[ordered_list_of_objectives[2]], s=20, c=solution.objective_values[ordered_list_of_objectives[4]], marker='o', lw=0, picker=5)
                        self.point.set_clim([self.lowerbounds[-1],self.upperbounds[-1]])

        self.picker = self.PopulationFigure.canvas.mpl_connect('pick_event', self.onpick)

    def onpick(self, event):
        #description = []
        #for objective_index in ordered_list_of_objectives:
        #    description = description + self.objective_column_headers[objective_index] + ': ' + str(
        ind = event.ind[0]
        print ind
        x, y, z = event.artist._offsets3d
        print self.solution_names[ind], x[ind], y[ind], z[ind]