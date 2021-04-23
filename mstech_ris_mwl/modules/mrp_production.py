from odoo import api, fields, models, _
import datetime

class MrpProduction(models.Model):
    _inherit = 'mrp.production'
    
    @api.multi
    def crear_xml_hl7_cita(self) :
        self.ensure_one()
        #MODELO: mrp.production
        #FUNCION: open_produce_product
        
        xml_subelement_separator = "\n        "
        xml_list = []
        h_t = 'MSH'
        
        def presentes_anidados(msh_ini, list_lists_elements) :
            element_list = []
            for list_elements in list_lists_elements :
                subelement_list = ["<" + h_t + "." + str(msh_ini) + ">"]
                for i in range(len(list_elements)) :
                    subelement_list += ["<" + h_t + "." + str(msh_ini) + "." + str(i+1) + ">" + list_elements[i] + "</" + h_t + "." + str(msh_ini) + "." + str(i+1) + ">"]
                element_list += [(xml_subelement_separator + "    ").join(subelement_list), "</" + h_t + "."+str(msh_ini) + ">"]
                #element_list += [(xml_subelement_separator + "    ").join(i and "<" + h_t + "." + str(msh_ini) + "." + str(i) + ">" + list_elements[i-1] + "</" + h_t + "." + str(msh_ini) + "." + str(i) + ">" or "<" + h_t + "." + str(msh_ini) + ">" for i in range(0,1+len(list_elements))), "</" + h_t + "."+str(msh_ini) + ">"]
                
                msh_ini = msh_ini + 1
            
            doc_return = xml_subelement_separator.join(element_list)
            #doc_return = xml_subelement_separator.join(j%2 and "</" + h_t + "."+str(msh_ini+j//2) + ">" or (xml_subelement_separator + "    ").join(i and "<" + h_t + "." + str(msh_ini+j//2) + "." + str(i) + ">" + list_lists_elements[j//2][i-1] + "</" + h_t + "." + str(msh_ini+j//2) + "." + str(i) + ">" or "<" + h_t + "." + str(msh_ini+j//2) + ">" for i in range(0,1+len(list_lists_elements[j//2]))) for j in range(2*len(list_lists_elements)))
            return doc_return
        
        def presentes_simples(msh_ini, list_elements) :
            #element_list = []
            #for i in range(msh_ini,msh_ini+len(list_elements)) :
            #    element_list += ["<" + h_t + "." + str(i) ">" + list_elements[i-msh_ini] + "</" + h_t + "." + str(i) + ">"]
            #doc_return = xml_subelement_separator.join(element_list)
            doc_return = xml_subelement_separator.join("<" + h_t + "." + str(i) + ">" + list_elements[i-msh_ini] + "</" + h_t + "." + str(i) + ">" for i in range(msh_ini,msh_ini+len(list_elements)))
            return doc_return
           
        def vacios_seguidos(inicio, fin=1) :
            doc_return = xml_subelement_separator.join("<" + h_t + "." + str(i) + "/>" for i in range(inicio, inicio + fin))
            return doc_return
        
        recepcion = self.x_studio_origen
        paciente = recepcion.partner_invoice_id
        medico = recepcion.x_studio_medico_referente
        examen = self.product_id
        
        #Cita: "MSH", "PID", "PV1", "ORC", "OBR", "ZDS"
        
        #MSH
        h_t = 'MSH'
        xml_sublist = ["<" + h_t + ">"]
        xml_sublist += [presentes_simples(1, ["|","^~\\&amp;"]), presentes_anidados(3,[['Odoo-RIS'],['RESONORTE'],['ActualPACS'],['PACS']])]
        xml_sublist += [presentes_anidados(7,[[datetime.datetime.now().strftime("%Y%m%d%H%M%S")]]), vacios_seguidos(8)]
        xml_sublist += [presentes_anidados(9,[['ORM','O01'],[str(recepcion.company_id.partner_id.vat)+str(self.id)],['P'],['2.2']]), vacios_seguidos(13,6)]
        xml_list += [xml_subelement_separator.join(xml_sublist), "</" + h_t + ">"]
        
        #PID
        h_t = 'PID'
        xml_sublist = ["<" + h_t + ">"]
        xml_sublist += [vacios_seguidos(1,2), presentes_anidados(3,[[str(paciente.id)]]), vacios_seguidos(4), presentes_anidados(5,[[paciente.name]])]
        xml_sublist += [vacios_seguidos(6), presentes_anidados(7,[[paciente.x_fecha_nacimiento.strftime("%Y%m%d%H%M%S")],[(paciente.x_studio_sexo or 'm').upper()[0]]])]
        xml_sublist += [vacios_seguidos(9,2), presentes_anidados(11,[[paciente.street]]), vacios_seguidos(12,8), presentes_anidados(20,[[paciente.vat]])]
        xml_list += [xml_subelement_separator.join(xml_sublist), "</" + h_t + ">"]
        
        #PV1
        h_t = 'PV1'
        xml_sublist = ["<" + h_t + ">"]
        xml_sublist += [vacios_seguidos(1), presentes_anidados(2,[['O']]), vacios_seguidos(3,4)]
        xml_sublist += [presentes_anidados(7,[[str(medico.id)]]), vacios_seguidos(8,2), presentes_anidados(10,[[self.product_id.name or "Examen"]])]
        xml_sublist += [vacios_seguidos(11,8), presentes_anidados(19,[[str(self.id)]]), vacios_seguidos(20,24)]
        xml_sublist += [presentes_anidados(44,[[datetime.datetime.now().strftime("%Y%m%d%H%M%S")]])]
        xml_list += [xml_subelement_separator.join(xml_sublist), "</" + h_t + ">"]
        
        #ORC
        h_t = 'ORC'
        xml_sublist = ["<" + h_t + ">"]
        xml_sublist += [presentes_anidados(1,[['NW'],[str(recepcion.id)]]), vacios_seguidos(3,4)]
        xml_sublist += [presentes_anidados(7,[[(recepcion.x_studio_agenda or datetime.datetime.now()).strftime("%Y%m%d%H%M%S")]]), vacios_seguidos(8)]
        xml_sublist += [presentes_anidados(9,[[(recepcion.confirmation_date or datetime.datetime.now()).strftime("%Y%m%d%H%M%S")]]), vacios_seguidos(10,5)]
        xml_sublist += [presentes_anidados(15,[[(recepcion.confirmation_date or datetime.datetime.now()).strftime("%Y%m%d%H%M%S")]])]
        xml_sublist += [presentes_anidados(16,[[recepcion.x_studio_observaciones or '']]), vacios_seguidos(17,2)]
        xml_sublist += [presentes_anidados(19,[[str(self.env.user.partner_id.id or 0)]])]
        xml_list += [xml_subelement_separator.join(xml_sublist), "</" + h_t + ">"]
        
        #OBR
        h_t = 'OBR'
        xml_sublist = ["<" + h_t + ">"]
        xml_sublist += [presentes_anidados(1,[['1']]), vacios_seguidos(2)]
        xml_sublist += [presentes_anidados(3,[[examen.default_code or '0000'],[examen.name.upper()]])]
        xml_sublist += [vacios_seguidos(5,5), presentes_anidados(10,[[recepcion.x_studio_sala.x_studio_aetitle],[recepcion.x_studio_sala.x_studio_aetitle,recepcion.x_studio_sala.x_studio_aetitle]]), vacios_seguidos(12,4)]
        xml_sublist += [presentes_anidados(16,[[medico.vat or '00000000',medico.name or 'DESCONOCIDO']]), vacios_seguidos(17)]
        xml_sublist += [presentes_anidados(18,[[recepcion.name],[recepcion.x_studio_sala.x_name+str(recepcion.id)]])]
        xml_sublist += [vacios_seguidos(20,4), presentes_anidados(24,[[examen.x_studio_modalidad.x_studio_codigo]])]
        xml_sublist += [vacios_seguidos(25,20)]
        xml_list += [xml_subelement_separator.join(xml_sublist), "</" + h_t + ">"]
        
        #ZDS
        h_t = 'ZDS'
        xml_sublist = ["<" + h_t + ">"]
        xml_sublist += [presentes_anidados(1,[['1.2.840.10009.' + recepcion.name[1:] + '.' + str(self.id).zfill(8)]])]
        xml_list += [xml_subelement_separator.join(xml_sublist), "</" + h_t + ">"]
        
        xml_doc = "<HL7Message>\n    " + "\n    ".join(xml_list) + "\n</HL7Message>"
        return xml_doc
    
    @api.multi
    def open_produce_product(self):
        for record in self:
            record.x_studio_mwl = True
        return super(MrpProduction, self).open_produce_product()
