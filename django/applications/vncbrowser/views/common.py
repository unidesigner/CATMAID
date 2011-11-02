from collections import defaultdict
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from vncbrowser.models import SORT_ORDERS_DICT, NeuronSearch, CELL_BODY_CHOICES, \
    ClassInstance, ClassInstanceClassInstance
import json

# Tip from: http://lincolnloop.com/blog/2008/may/10/getting-requestcontext-your-templates/
# Required because we need a RequestContext, not just a Context - the
# former looks at TEMPLATE_CONTEXT_PROCESSORS, while the latter doesn't.

def my_render_to_response(req, *args, **kwargs):
    kwargs['context_instance'] = RequestContext(req)
    return render_to_response(*args, **kwargs)

# When an operation fails we should return a JSON dictionary
# with the key 'error' set to an error message.  This is a
# helper method to return such a structure:
def json_error_response(message):
    return HttpResponse(json.dumps({'error': message}),
                        mimetype='text/json')

def order_neurons( neurons, order_by = None ):
    column, reverse = 'name', False
    if order_by and (order_by in SORT_ORDERS_DICT):
        column, reverse, _ = SORT_ORDERS_DICT[order_by]
        if column == 'name':
            neurons.sort(key=lambda x: x.name)
        elif column == 'gal4':
            neurons.sort(key=lambda x: x.cached_sorted_lines_str)
        elif column == 'cell_body':
            neurons.sort(key=lambda x: x.cached_cell_body)
        else:
            raise Exception, "Unknown column (%s) in order_neurons" % (column,)
        if reverse:
            neurons.reverse()
    return neurons

# Both index and visual_index take a request and kwargs and then
# return a list of neurons and a NeuronSearch form:

def get_form_and_neurons(request, project_id, kwargs):
    # If we've been passed parameters in a REST-style GET request,
    # create a form from them.  Otherwise, if it's a POST request,
    # create the form from the POST parameters.  Otherwise, it's a
    # plain request, so create the default search form.
    rest_keys = ('search','cell_body_location','order_by')
    if any((x in kwargs) for x in rest_keys):
        kw_search = kwargs.get('search',None) or ""
        kw_cell_body_choice = kwargs.get('cell_body_location',None) or "a"
        kw_order_by = kwargs.get('order_by',None) or 'name'
        search_form = NeuronSearch({'search': kw_search,
                                    'cell_body_location': kw_cell_body_choice,
                                    'order_by': kw_order_by })
    elif request.method == 'POST':
        search_form = NeuronSearch(request.POST)
    else:
        search_form = NeuronSearch({'search': '',
                                    'cell_body_location': 'a',
                                    'order_by': 'name'})
    if search_form.is_valid():
        search = search_form.cleaned_data['search']
        cell_body_location = search_form.cleaned_data['cell_body_location']
        order_by = search_form.cleaned_data['order_by']
    else:
        search = ''
        cell_body_location = 'a'
        order_by = 'name'

    cell_body_choices_dict = dict(CELL_BODY_CHOICES)

    all_neurons = ClassInstance.objects.filter(
        project__id=project_id,
        class_column__class_name='neuron',
        name__icontains=search).exclude(name='orphaned pre').exclude(name='orphaned post')

    if cell_body_location != 'a':
        location = cell_body_choices_dict[cell_body_location]
        all_neurons = all_neurons.filter(
            project__id=project_id,
            cici_via_a__relation__relation_name='has_cell_body',
            cici_via_a__class_instance_b__name=location)

    cici_qs = ClassInstanceClassInstance.objects.filter(
        project__id=project_id,
        relation__relation_name='has_cell_body',
        class_instance_a__class_column__class_name='neuron',
        class_instance_b__class_column__class_name='cell_body_location')

    neuron_id_to_cell_body_location = dict(
        (x.class_instance_a.id, x.class_instance_b.name) for x in cici_qs)

    neuron_id_to_driver_lines = defaultdict(list)

    for cici in ClassInstanceClassInstance.objects.filter(
        project__id=project_id,
        relation__relation_name='expresses_in',
        class_instance_a__class_column__class_name='driver_line',
        class_instance_b__class_column__class_name='neuron'):
        neuron_id_to_driver_lines[cici.class_instance_b.id].append(cici.class_instance_a)

    all_neurons = list(all_neurons)

    for n in all_neurons:
        n.cached_sorted_lines = sorted(
            neuron_id_to_driver_lines[n.id], key=lambda x: x.name)
        n.cached_sorted_lines_str = ", ".join(x.name for x in n.cached_sorted_lines)
        n.cached_cell_body = neuron_id_to_cell_body_location.get(n.id, 'Unknown')

    all_neurons = order_neurons(all_neurons, order_by)
    return (all_neurons, search_form)
